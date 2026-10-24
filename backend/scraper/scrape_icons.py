"""补抓物品图标 URL（一次性种子数据增强）。

官方开放 API 的**列表接口不返回 icon**，只有详情接口有：
    GET /items/{id} -> {..., "icon": "https://wowforever.wclbox.com/tubiao/inv_ingot_02.jpg"}

图标就是无限版客户端资源（inv_ingot_02 / spell_xxx 命名与原版同一套体系，
且无限新增物品原版 wowhead 反而没有），所以无需去爬原版站点。

输入/输出：backend/data/items.json（就地补充 icon 字段）
断点：backend/data/icons_progress.json（{id: icon_url | null}）

用法：
    python scrape_icons.py
"""

from __future__ import annotations

import argparse
import json
import time
import urllib.error
import urllib.request
from pathlib import Path

BASE = "https://wowforever.wclbox.com/api/open/v1"
MIN_INTERVAL = 0.2  # 官方限流 5 次/秒，留余量
TIMEOUT = 30
MAX_RETRIES = 4

_last_call = 0.0


def _rate_limit() -> None:
    global _last_call
    wait = MIN_INTERVAL - (time.monotonic() - _last_call)
    if wait > 0:
        time.sleep(wait)
    _last_call = time.monotonic()


def api_get(path: str) -> dict:
    url = f"{BASE}{path}"
    for attempt in range(1, MAX_RETRIES + 1):
        _rate_limit()
        req = urllib.request.Request(url, headers={"User-Agent": "WoW-F-BussinessClac-seed/1.0"})
        try:
            with urllib.request.urlopen(req, timeout=TIMEOUT) as resp:
                return json.loads(resp.read().decode("utf-8"))
        except (urllib.error.URLError, urllib.error.HTTPError, TimeoutError, json.JSONDecodeError) as exc:
            if attempt == MAX_RETRIES:
                raise RuntimeError(f"请求失败 {url}: {exc}") from exc
            time.sleep(2.0 * attempt)
    raise RuntimeError("unreachable")


def main() -> None:
    ap = argparse.ArgumentParser()
    root = Path(__file__).resolve().parents[2]
    ap.add_argument("--items", default=str(root / "backend" / "data" / "items.json"))
    ap.add_argument("--progress", default=str(root / "backend" / "data" / "icons_progress.json"))
    args = ap.parse_args()

    items_path = Path(args.items)
    items: list[dict] = json.loads(items_path.read_text(encoding="utf-8"))["items"]

    progress_path = Path(args.progress)
    progress: dict[str, str | None] = {}
    if progress_path.exists():
        progress = json.loads(progress_path.read_text(encoding="utf-8"))

    todo = [it["id"] for it in items if str(it["id"]) not in progress]
    print(f"物品 {len(items)} 个，待抓图标 {len(todo)} 个（已完成 {len(progress)} 个）", flush=True)

    done = 0
    failed = 0
    for item_id in todo:
        try:
            detail = api_get(f"/items/{item_id}")
            icon = detail.get("icon") or None
            progress[str(item_id)] = icon
            done += 1
            if done % 200 == 0:
                progress_path.write_text(json.dumps(progress), encoding="utf-8")
                print(f"图标进度 {done}/{len(todo)}", flush=True)
        except RuntimeError as exc:
            print(f"[warn] {exc}，稍后重跑可续传", flush=True)
            failed += 1
            if failed >= 3:
                break
    progress_path.write_text(json.dumps(progress), encoding="utf-8")

    # 合并回 items.json
    got = 0
    for it in items:
        icon = progress.get(str(it["id"]))
        if icon:
            it["icon"] = icon
            got += 1
        else:
            it["icon"] = None
    items_path.write_text(
        json.dumps({"items": items}, ensure_ascii=False, indent=1),
        encoding="utf-8",
    )
    print(f"\n完成：{got}/{len(items)} 个物品有图标 -> {items_path}")


if __name__ == "__main__":
    main()
