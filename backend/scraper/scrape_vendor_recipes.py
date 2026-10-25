"""抓取「商人青睐配方」：贸易营地出售的专业配方及其青睐价格。

数据源：无限官方中文数据库专题页 https://wowforever.wclbox.com/shangren

页尾「全部 313 种配方」按专业分组，每个专业下再按「青睐档位」列出：

    <section id="blacksmithing" class="zn-section zn-anchor">
      <h2 class="zn-h2 sr-prof">
        锻造 <small>出售者：斯通德里·暗锤（联盟）或 戈尔马克（部落）</small>
      </h2>
      <div class="zn-tier">
        <h3 class="zn-h3">30 商人青睐<small>30 个配方，技能 45 至 125</small></h3>
        <ul class="zn-crafted">
          <li><a data-tip="250513" href="/wupin/250513"><span class="q3">老兵的链甲腰带</span></a>
              <span class="zn-skill zn-c-orange">45</span></li>
          ...

关键事实（官方原文）：
  * 联盟营地 = **艾泽拉斯贸易局**（赤脊山 · 三角路口）
    部落营地 = **杜隆塔尔补给后勤部**（贫瘠之地 · 十字路口）
    —— 两处营地出售的配方和价格**相同**，只是 NPC 不同。
  * 购买货币是「**商人青睐**」，靠上交装满材料的**板条箱**获得，**不是声望**。
    官方原话：「配方没有声望要求。营地声望只影响 2 件商品」
  * 「营地声望」来自**工匠文书**（密封的工匠文书 → 制造订单 → 交付物品）。

输出：backend/data/vendor_recipes.json
    {
      "<profession_key>": {
        "alliance": {"npc": "斯通德里·暗锤", "camp": "艾泽拉斯贸易局", "zone": "赤脊山 · 三角路口", "coord": "10.4, 74.5"},
        "horde":    {"npc": "戈尔马克", "camp": "杜隆塔尔补给后勤部", "zone": "贫瘠之地 · 十字路口", "coord": "49.8, 29.6"},
        "by_item": {"<成品物品 ID>": {"favor": 30, "name": "老兵的链甲腰带", "skill": 45}, ...}
      }, ...
    }

用法：
    python scrape_vendor_recipes.py                # 抓全部专业
    python scrape_vendor_recipes.py blacksmithing  # 只抓指定专业
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

PAGE_URL = "https://wowforever.wclbox.com/shangren"
UA = {"User-Agent": "WoW-F-BussinessClac-seed/1.0 (+vendor-recipes)"}
TIMEOUT = 60
MAX_RETRIES = 3

OUT_FILE = Path(__file__).resolve().parents[1] / "data" / "vendor_recipes.json"

# 站点 slug → 本项目 profession key（本项目少了钓鱼/剥皮/野营）
SLUG_TO_KEY = {
    "alchemy": "alchemy",
    "blacksmithing": "blacksmithing",
    "cooking": "cooking",
    "enchanting": "enchanting",
    "engineering": "engineering",
    "leatherworking": "leatherworking",
    "tailoring": "tailoring",
}

# 站点专业 slug → 中文名（用于把 zn-section 的 id 对上）
SLUG_NAMES = {
    "alchemy": "炼金术",
    "blacksmithing": "锻造",
    "cooking": "烹饪",
    "enchanting": "附魔",
    "engineering": "工程学",
    "leatherworking": "制皮",
    "tailoring": "裁缝",
}


def fetch(url: str) -> str:
    for attempt in range(1, MAX_RETRIES + 1):
        try:
            with urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=TIMEOUT) as r:
                return r.read().decode("utf-8", "ignore")
        except (urllib.error.URLError, urllib.error.HTTPError, TimeoutError) as exc:
            if attempt == MAX_RETRIES:
                raise RuntimeError(f"请求失败 {url}: {exc}") from exc
            time.sleep(2.0 * attempt)
    raise RuntimeError("unreachable")


def _text(raw: str) -> str:
    s = re.sub(r"<!--.*?-->", "", raw, flags=re.S)
    s = re.sub(r"<[^>]+>", "", s)
    s = html.unescape(s)
    return re.sub(r"\s+", " ", s).strip()


def _parse_vendors(section: str) -> tuple[dict | None, dict | None]:
    """从 <h2> 的「出售者：NPC（联盟）或 NPC（部落）」里抠出两个阵营的卖家信息。

    格式：<small>出售者：<span><a ...>斯通德里·暗锤</a>（联盟）</span>
          <span>或 <a ...>戈尔马克</a>（部落）</span></small>
    """
    h2 = re.search(r"<h2 class=\"zn-h2 sr-prof\">(.*?)</h2>", section, re.S)
    if not h2:
        return None, None
    head = h2.group(1)
    out: dict[str, dict] = {}
    for side, npc in re.findall(r'href="/ditu/[^"]*"[^>]*>([^<]+)</a>（(联盟|部落)）', head):
        pass
    # 「（联盟）」/「（部落）」标在 a 标签之后
    for m in re.finditer(r"<a [^>]*>([^<]+)</a>（(联盟|部落)）", head):
        out[m.group(2)] = {"npc": _text(m.group(1))}
    # 营地名 + 坐标在「营地人员」表里，专业页与专题页各有一份；这里从专题页 sr-guide-people 取
    return out.get("联盟"), out.get("部落")


def parse_camps(page: str) -> dict[str, dict]:
    """从「贸易营地」小节取两处营地名称与坐标。

    结构：<div class="yd sr-guide-camp sr-guide-camp-a">
              <span class="sr-guide-side">联盟营地</span>
              <strong>艾泽拉斯贸易局</strong>
              <span>赤脊山 · 三角路口</span>
              <span class="sr-guide-muted">10.2, 72.5</span>
              <span>板条箱交给<b>玛茜·贝克</b>。</span>
    """
    camps: dict[str, dict] = {}
    for m in re.finditer(
        r'<div class="yd sr-guide-camp sr-guide-camp-(\w)">(.*?)</div>', page, re.S
    ):
        side = "alliance" if m.group(1) == "a" else "horde"
        body = m.group(2)
        camp = re.search(r"<strong>([^<]+)</strong>", body)
        spans = re.findall(r"<span[^>]*>(.*?)</span>", body, re.S)
        texts = [_text(s) for s in spans]
        # 第一个 span 是「联盟营地 / 部落营地」标签，第二个是区域名（赤脊山 · 三角路口）
        zone = ""
        for t in texts:
            if re.search(r"[\u4e00-\u9fa5]", t) and "营地" not in t and "," not in t:
                zone = t
                break
        coord = next((t for t in texts if re.fullmatch(r"[\d.]+,\s*[\d.]+", t)), "")
        crate = re.search(r"板条箱交给<b>([^<]+)</b>", body)
        camps[side] = {
            "camp": _text(camp.group(1)) if camp else "",
            "zone": zone,
            "coord": coord.replace(" ", ""),
            "crate_npc": _text(crate.group(1)) if crate else "",
        }
    return camps


def parse_page(page: str) -> dict[str, dict]:
    """解析专题页 → {profession_key: {...}}。"""
    camps = parse_camps(page)

    result: dict[str, dict] = {}
    for m in re.finditer(
        r'<section id="([a-z]+)" class="zn-section zn-anchor">(.*?)(?=<section id="|$)', page, re.S
    ):
        slug, section = m.group(1), m.group(2)
        key = SLUG_TO_KEY.get(slug)
        if not key:
            continue

        alliance, horde = _parse_vendors(section)

        by_item: dict[str, dict] = {}
        for tm in re.finditer(r'<div class="zn-tier">(.*?)</div>\s*(?=<div class="zn-tier">|</section>)', section, re.S):
            tier = tm.group(1)
            fav = re.search(r"<h3[^>]*>\s*([\d,]+)\s*商人青睐", tier)
            if not fav:
                continue
            favor = int(fav.group(1).replace(",", ""))
            for lm in re.finditer(r"<li>(.*?)</li>", tier, re.S):
                li = lm.group(1)
                iid = re.search(r"data-tip=\"(\d+)\"", li)
                nm = re.search(r'<span class="q\d">([^<]+)</span>', li)
                sk = re.search(r'<span class="zn-skill[^"]*">(\d+)</span>', li)
                if not iid:
                    continue
                by_item[iid.group(1)] = {
                    "favor": favor,
                    "name": _text(nm.group(1)) if nm else "",
                    "skill": int(sk.group(1)) if sk else None,
                }

        if not by_item:
            continue

        entry: dict = {"by_item": by_item}
        if alliance:
            entry["alliance"] = alliance
        if horde:
            entry["horde"] = horde
        for side in ("alliance", "horde"):
            if side in camps:
                entry[side] = {**entry.get(side, {}), **camps[side]}
        result[key] = entry
    return result


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("slugs", nargs="*", default=list(SLUG_TO_KEY))
    ap.add_argument("--out", default=str(OUT_FILE))
    args = ap.parse_args()

    page = fetch(PAGE_URL)
    print(f"专题页 {len(page)} 字节", flush=True)

    parsed = parse_page(page)
    result: dict[str, dict] = {}
    out_path = Path(args.out)
    if out_path.exists():
        result = json.loads(out_path.read_text(encoding="utf-8"))

    total = 0
    for slug in args.slugs:
        key = SLUG_TO_KEY.get(slug)
        if key is None or key not in parsed:
            print(f"{slug:16s} 跳过（页面无此专业）", flush=True)
            continue
        result[key] = parsed[key]
        n = len(parsed[key]["by_item"])
        total += n
        a = parsed[key].get("alliance", {})
        h = parsed[key].get("horde", {})
        print(
            f"{key:16s} {n:4d} 个配方 | 联盟 {a.get('npc','?')}({a.get('camp','?')}) "
            f"| 部落 {h.get('npc','?')}({h.get('camp','?')})",
            flush=True,
        )

    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(result, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"\n已写入 {out_path}（{len(result)} 个专业 / {total} 个配方）")


if __name__ == "__main__":
    sys.exit(main())
