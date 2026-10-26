"""抓取物品「游戏内 tooltip」全文（用于鼠标悬停信息卡）。

官方开放 API：GET /items/{id} 返回 tooltip 字段，就是游戏里那一整块文本的逐行数组，
例如雕花皮外衣：

    ["装备后绑定", "胸部\\t皮甲", "护甲值 62", "+2 耐力", "需要等级 7", "售价：1银92铜"]

这就是「跟游戏内置一样的功能介绍说明」的数据来源，比 wowhead 更贴合本服（无限测试版）
数据；而且 tooltip 行里天然带 \\t 分隔的左右两列（部位/护甲类型），渲染时照搬即可。

输入：backend/data/items.json（物品 ID 清单）
输出：backend/data/item_tooltips.json   {"items": {"<id>": {"tooltip": [...], "slot": ...}}}
断点续传：item_tooltips_progress.json 记录已完成的 ID，中断后重跑自动续上。

用法：
    python scrape_tooltips.py            # 全部
    python scrape_tooltips.py --limit 50 # 先跑 50 个看看
"""

from __future__ import annotations

import argparse
import json
import time
import urllib.error
import urllib.request
from pathlib import Path

BASE = "https://wowforever.wclbox.com/api/open/v1"
DATA_DIR = Path(__file__).resolve().parent.parent / "data"
OUT_FILE = DATA_DIR / "item_tooltips.json"
PROGRESS_FILE = DATA_DIR / "item_tooltips_progress.json"
ITEMS_FILE = DATA_DIR / "items.json"

MIN_INTERVAL = 0.21  # 秒；官方限流 5 次/秒，留余量
TIMEOUT = 20
MAX_RETRIES = 3

_last_call = 0.0


def _rate_limit() -> None:
    global _last_call
    wait = MIN_INTERVAL - (time.monotonic() - _last_call)
    if wait > 0:
        time.sleep(wait)
    _last_call = time.monotonic()


def api_get(path: str) -> dict:
    url = f"{BASE}{path}"
    last_exc: Exception | None = None
    for attempt in range(1, MAX_RETRIES + 1):
        _rate_limit()
        req = urllib.request.Request(url, headers={"User-Agent": "WoW-F-BussinessClac-seed/1.0"})
        try:
            with urllib.request.urlopen(req, timeout=TIMEOUT) as resp:
                return json.loads(resp.read().decode("utf-8"))
        except (urllib.error.URLError, urllib.error.HTTPError, TimeoutError, json.JSONDecodeError) as exc:
            last_exc = exc
            if attempt == MAX_RETRIES:
                break
            time.sleep(2.0 * attempt)
    raise RuntimeError(f"请求失败 {url}: {last_exc}")


def load_json(path: Path, default):
    if not path.exists():
        return default
    with path.open(encoding="utf-8") as f:
        return json.load(f)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--limit", type=int, default=0, help="只处理前 N 个（调试用）")
    args = ap.parse_args()

    items = load_json(ITEMS_FILE, {"items": []})["items"]
    ids = [int(it["id"]) for it in items]
    if args.limit:
        ids = ids[: args.limit]

    store: dict[str, dict] = load_json(OUT_FILE, {"items": {}})["items"]
    done: set[str] = set(load_json(PROGRESS_FILE, {"done": []})["done"])

    todo = [i for i in ids if str(i) not in done]
    print(f"物品总数 {len(ids)}，已完成 {len(ids) - len(todo)}，待抓 {len(todo)}", flush=True)

    for n, iid in enumerate(todo, 1):
        try:
            d = api_get(f"/items/{iid}")
        except RuntimeError as exc:
            print(f"[跳过] {iid}: {exc}", flush=True)
            continue
        tooltip = d.get("tooltip") or []
        store[str(iid)] = {
            "tooltip": tooltip,
            "tooltip_en": d.get("tooltipEn") or [],
            "slot": d.get("slot"),
            "set": d.get("set"),
            "classes": d.get("classes") or [],
        }
        done.add(str(iid))
        if n % 50 == 0 or n == len(todo):
            OUT_FILE.write_text(
                json.dumps({"items": store}, ensure_ascii=False, indent=0), encoding="utf-8"
            )
            PROGRESS_FILE.write_text(
                json.dumps({"done": sorted(done, key=int)}), encoding="utf-8"
            )
            print(f"进度 {n}/{len(todo)}", flush=True)

    OUT_FILE.write_text(json.dumps({"items": store}, ensure_ascii=False, indent=0), encoding="utf-8")
    PROGRESS_FILE.write_text(json.dumps({"done": sorted(done, key=int)}), encoding="utf-8")
    print(f"完成：{len(store)} 条写入 {OUT_FILE}", flush=True)


if __name__ == "__main__":
    main()
