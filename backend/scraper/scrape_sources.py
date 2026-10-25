"""抓取「配方来源」：每个成品的图纸/配方从哪儿来。

数据源：无限官方中文数据库的专业页 https://wowforever.wclbox.com/zhuanye/<slug>
页面里有一张「配方大全」表，最后一列就是「来源」，例如：

    训练师
    商人 · 罗克图斯·暗契
    商人林沃斯 · 荆棘谷
    世界掉落 · 怪物 10–63 级
    开启 秘银宝箱
    掉落 · 古拉鲁克 · 黑石塔
    任务 · [联] 前线的补给
    出没 · 奥特兰克山脉、洛克莫丹、贫瘠之地

比 /wupin/<id> 页面里那句「来源：商人，2 个地区」细得多（有 NPC 名和地区），
也解决了 wowhead 抓不到的问题（www.wowhead.com 403，nether 版 tooltip 无来源字段）。

输出：backend/data/recipe_sources.json
    {
      "<profession_key>": {
        "by_item": { "<制成品物品 ID>": "来源文本", ... },
        "by_name": { "<规范化配方名>": "来源文本", ... }
      }, ...
    }

附魔的成品没有物品 ID，只能按名匹配，所以额外存一份 by_name（已去掉
「公式：」等前缀和「（+2 耐力）」这类括号后缀）。

用法：
    python scrape_sources.py                # 抓全部专业
    python scrape_sources.py blacksmithing  # 只抓指定专业
"""

from __future__ import annotations

import argparse
import html
import json
import re
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

BASE = "https://wowforever.wclbox.com/zhuanye"
UA = {"User-Agent": "WoW-F-BussinessClac-seed/1.0 (+sources)"}
MIN_INTERVAL = 1.0  # 秒；HTML 页面，礼貌抓取
TIMEOUT = 60
MAX_RETRIES = 3

OUT_FILE = Path(__file__).resolve().parents[1] / "data" / "recipe_sources.json"

_last_call = 0.0


def _rate_limit() -> None:
    global _last_call
    wait = MIN_INTERVAL - (time.monotonic() - _last_call)
    if wait > 0:
        time.sleep(wait)
    _last_call = time.monotonic()


def fetch(slug: str) -> str:
    url = f"{BASE}/{slug}"
    for attempt in range(1, MAX_RETRIES + 1):
        _rate_limit()
        try:
            with urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=TIMEOUT) as r:
                return r.read().decode("utf-8", "ignore")
        except (urllib.error.URLError, urllib.error.HTTPError, TimeoutError) as exc:
            if attempt == MAX_RETRIES:
                raise RuntimeError(f"请求失败 {url}: {exc}") from exc
            time.sleep(2.0 * attempt)
    raise RuntimeError("unreachable")


def _extract_span(seg: str, open_tag_end: int) -> str:
    """从 <span ...> 的结束位置开始，按嵌套深度取回配对的 </span> 之前的内容。"""
    depth = 1
    i = open_tag_end
    while i < len(seg) and depth > 0:
        nxt_open = seg.find("<span", i)
        nxt_close = seg.find("</span>", i)
        if nxt_close < 0:
            break
        if 0 <= nxt_open < nxt_close:
            depth += 1
            i = nxt_open + 5
        else:
            depth -= 1
            i = nxt_close + 7
    return seg[open_tag_end : max(0, i - 7)]


def _clean(raw: str) -> str:
    """把来源单元格的 HTML 变成一行可读中文。"""
    s = raw
    # 阵营标记 <i class="zk-side zk-side-a">联</i> → [联]
    s = re.sub(r'<i class="zk-side[^"]*">(.)</i>', r"[\1]", s)
    # 去掉 React 的注释分隔符
    s = re.sub(r"<!--.*?-->", "", s, flags=re.S)
    # 链接保留文字
    s = re.sub(r"<[^>]+>", "", s)
    s = html.unescape(s)
    s = re.sub(r"\s+", " ", s).strip()
    return s


# 附魔行的 zk-made 是 <span class="zk-item">，没有 data-item，且名字里带 <small>耐力 +2</small>
NAME_RE = re.compile(r'<span class="zk-name[^"]*">(.*?)</span>', re.S)


def normalize_name(name: str) -> str:
    """规范化配方名用于匹配：去「公式：」等前缀、去「（…）」后缀、去所有空白。"""
    s = re.sub(r"<small>.*?</small>", "", name, flags=re.S)  # 附魔名里的「耐力 +2」
    s = re.sub(r"<[^>]+>", "", s)
    s = re.sub(r"^.*?[：:]\s*", "", s) if re.match(r"^(公式|设计图|图样|结构图|配方|图纸)", s) else s
    s = re.sub(r"[（(].*?[)）]", "", s)
    return re.sub(r"\s+", "", s).strip()


def parse_page(page: str) -> dict[str, dict[str, str]]:
    """解析专业页配方表 → {by_item: {...}, by_name: {...}}。

    注意：页面把配方拆成两张 zk-recipes 表——前 120 行直接渲染，
    其余装在 <details class="zk-recipe-rest"> 里（展开其余 N 项），
    但折叠内容同样在 HTML 里，两张都要解析。
    """
    tables: list[str] = []
    pos = 0
    while True:
        start = page.find('<table class="zk-table zk-recipes">', pos)
        if start < 0:
            break
        end = page.find("</table>", start)
        tables.append(page[start:end])
        pos = end + 8
    if not tables:
        raise RuntimeError("页面里找不到配方表 zk-recipes")

    by_item: dict[str, str] = {}
    by_name: dict[str, str] = {}
    for table in tables:
        _parse_table(table, by_item, by_name)
    return {"by_item": by_item, "by_name": by_name}


def _parse_table(table: str, by_item: dict[str, str], by_name: dict[str, str]) -> None:
    for row in re.split(r"<tr[\s>]", table)[1:]:
        made_at = row.find('<span class="zk-made">')
        if made_at < 0:
            continue
        made = row[made_at : row.find("</span></span>", made_at) + 8]
        id_m = re.search(r'data-item="(\d+)"', made)
        name_m = NAME_RE.search(made)
        item_id = id_m.group(1) if id_m else ""
        name = normalize_name(name_m.group(1)) if name_m else ""
        if not item_id and not name:
            continue

        # 来源：来源列是最后一个 <td>，里面可能有 1~2 个 zk-src-t
        # （例如「出没 · 洛克莫丹、贫瘠之地、赤脊山」+「开启 瓶中信」）
        cell = row[row.rfind("<td>") :]
        texts: list[str] = []
        pos = 0
        while True:
            m = re.search(r'<span class="zk-src-t"[^>]*>', cell[pos:])
            if not m:
                break
            at = pos + m.end()
            texts.append(_clean(_extract_span(cell, at)))
            pos = at
        text = "；".join(t for t in texts if t)
        if not text:
            # 只有图纸名、站点没给出处 → 记为未知，不把图纸名当来源
            continue
        if item_id:
            by_item[item_id] = text
        if name:
            by_name.setdefault(name, text)
    return


PROFESSIONS = [
    "blacksmithing",
    "leatherworking",
    "tailoring",
    "alchemy",
    "enchanting",
    "engineering",
    "cooking",
    "first-aid",
    "mining",
]


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("slugs", nargs="*", default=PROFESSIONS)
    ap.add_argument("--out", default=str(OUT_FILE))
    args = ap.parse_args()

    result: dict[str, dict] = {}
    out_path = Path(args.out)
    if out_path.exists():
        result = json.loads(out_path.read_text(encoding="utf-8"))

    for slug in args.slugs:
        page = fetch(slug)
        rows = parse_page(page)
        result[slug] = rows
        print(f"{slug:16s} by_item {len(rows['by_item']):4d} / by_name {len(rows['by_name']):4d}", flush=True)
        for k, v in list(rows["by_item"].items())[:2]:
            print(f"    {k} → {v}")

    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(result, ensure_ascii=False, indent=1), encoding="utf-8")
    total = sum(len(v["by_item"]) for v in result.values())
    print(f"\n已写入 {out_path}（{len(result)} 个专业 / {total} 条）")


if __name__ == "__main__":
    sys.exit(main())
