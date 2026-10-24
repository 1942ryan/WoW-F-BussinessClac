"""通过官方开放 API 抓取物品主数据与卖店价（一次性的种子数据生成）。

API: https://wowforever.wclbox.com/api/open/v1 （免登录、限流 5 次/秒/IP）
- GET /items?ids=a,b,c   批量主数据，最多 100 个/请求
- GET /items/{id}        详情，tooltip 含「售价：X铜」

输入：backend/data/professions.json（由 scrape_professions.py 生成）
输出：backend/data/items.json

用法：
    python scrape_items.py [--with-designs] [--out FILE]

说明：
- 主数据（名称/品质/类型）覆盖全部被引用的物品（含设计图）；
- 卖店价只抓「成品 + 材料」类物品（--with-designs 时也抓设计图）；
- 支持断点续传：已完成的 ID 记录在 items_progress.json，中断后重跑自动跳过。
"""

from __future__ import annotations

import argparse
import json
import re
import time
import urllib.error
import urllib.request
from pathlib import Path

BASE = "https://wowforever.wclbox.com/api/open/v1"
MIN_INTERVAL = 0.22  # 秒；官方限流 5 次/秒，留余量
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
            time.sleep(2.0 * attempt)  # 指数退避
    raise RuntimeError("unreachable")


def parse_sell_price(tooltip: list[str], tooltip_en: list[str]) -> int:
    """从 tooltip 行解析卖店价，返回铜数；无法解析返回 0。"""
    def to_copper(num: float, unit: str) -> int:
        factor = {"金": 10000, "银": 100, "铜": 1, "g": 10000, "s": 100, "c": 1}
        return int(round(num * factor.get(unit, 1)))

    for line in tooltip:
        m = re.search(r"售价：\s*([\d.]+)\s*([金银铜])", line)
        if m:
            return to_copper(float(m.group(1)), m.group(2))
        m = re.search(r"售价：\s*(\d+)\s*([金银铜])\s*(\d+)\s*([金银铜])", line)
        if m:
            return to_copper(float(m.group(1)), m.group(2)) + to_copper(float(m.group(3)), m.group(4))
    for line in tooltip_en:
        m = re.search(r"Sell Price:\s*([\d.]+)\s*([gsc])", line, re.I)
        if m:
            return to_copper(float(m.group(1)), m.group(2).lower())
        m = re.search(r"Sell Price:\s*(\d+)\s*([gsc])\s*(\d+)\s*([gsc])", line, re.I)
        if m:
            return to_copper(float(m.group(1)), m.group(2).lower()) + to_copper(
                float(m.group(3)), m.group(4).lower()
            )
    return 0


def collect_item_ids(professions: list[dict]) -> tuple[set[int], set[int]]:
    """返回 (全部被引用物品, 成品+材料物品)。"""
    all_ids: set[int] = set()
    prod_mat: set[int] = set()
    for prof in professions:
        for rec in prof["recipes"]:
            if rec["product"]["item_id"]:
                all_ids.add(rec["product"]["item_id"])
                prod_mat.add(rec["product"]["item_id"])
            if rec["source"]["item_id"]:
                all_ids.add(rec["source"]["item_id"])
            for mat in rec["materials"]:
                all_ids.add(mat["item_id"])
                prod_mat.add(mat["item_id"])
    return all_ids, prod_mat


def main() -> None:
    ap = argparse.ArgumentParser()
    root = Path(__file__).resolve().parents[2]
    ap.add_argument("--professions", default=str(root / "backend" / "data" / "professions.json"))
    ap.add_argument("--out", default=str(root / "backend" / "data" / "items.json"))
    ap.add_argument("--progress", default=str(root / "backend" / "data" / "items_progress.json"))
    ap.add_argument("--with-designs", action="store_true", help="设计图也抓卖店价")
    args = ap.parse_args()

    data = json.loads(Path(args.professions).read_text(encoding="utf-8"))
    all_ids, prod_mat = collect_item_ids(data["professions"])
    need_price = prod_mat | (all_ids if args.with_designs else set())
    print(f"被引用物品 {len(all_ids)} 个，其中需要卖店价 {len(need_price)} 个")

    # ---- 1. 主数据（批量） ----
    items: dict[int, dict] = {}
    ids_sorted = sorted(all_ids)
    missing_ids: set[int] = set()
    for i in range(0, len(ids_sorted), 100):
        chunk = ids_sorted[i : i + 100]
        resp = api_get("/items?ids=" + ",".join(map(str, chunk)) + "&limit=100")
        got = {it["id"] for it in resp.get("items", [])}
        missing_ids.update(set(chunk) - got)
        for it in resp.get("items", []):
            items[it["id"]] = {
                "id": it["id"],
                "name": it["name"],
                "name_en": it.get("nameEn"),
                "quality": it.get("quality", 0),
                "item_level": it.get("itemLevel"),
                "required_level": it.get("requiredLevel"),
                "type": it.get("type"),
                "class_id": it.get("classId"),
                "status": it.get("status"),
                "vendor_price": 0,
            }
        print(f"主数据进度 {min(i + 100, len(ids_sorted))}/{len(ids_sorted)}", flush=True)
    if missing_ids:
        print(f"[warn] {len(missing_ids)} 个 ID 在官方库中不存在（数据库未收录）", flush=True)

    # ---- 2. 卖店价（详情，断点续传） ----
    progress_path = Path(args.progress)
    progress: dict[str, int] = {}
    if progress_path.exists():
        progress = json.loads(progress_path.read_text(encoding="utf-8"))
    todo = [i for i in sorted(need_price) if str(i) not in progress and i in items]
    print(f"待抓卖店价 {len(todo)} 个（已完成 {len(progress)} 个）", flush=True)

    done = 0
    for item_id in todo:
        try:
            detail = api_get(f"/items/{item_id}")
            price = parse_sell_price(detail.get("tooltip", []), detail.get("tooltipEn", []))
            if item_id in items:
                items[item_id]["vendor_price"] = price
            progress[str(item_id)] = price
            done += 1
            if done % 100 == 0:
                progress_path.write_text(json.dumps(progress), encoding="utf-8")
                print(f"卖店价进度 {done}/{len(todo)}", flush=True)
        except RuntimeError as exc:
            print(f"[warn] {exc}，稍后重跑可续传", flush=True)
            break
    progress_path.write_text(json.dumps(progress), encoding="utf-8")

    # ---- 3. 输出 ----
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(
        json.dumps({"items": [items[k] for k in sorted(items)]}, ensure_ascii=False, indent=1),
        encoding="utf-8",
    )
    have_price = sum(1 for it in items.values() if it["vendor_price"] > 0)
    print(f"\n完成：{len(items)} 个物品（{have_price} 个有卖店价）-> {out}")


if __name__ == "__main__":
    main()
