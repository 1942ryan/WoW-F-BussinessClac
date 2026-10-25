"""种子数据加载：professions.json + items.json → 数据库。

用法：
    python -m app.seed            # 仅当专业表为空时加载
    python -m app.seed --force    # 清空重建配方相关数据
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

from sqlalchemy import delete, select

from .database import SessionLocal, init_db
from .models import Item, MaterialSource, Profession, Recipe, RecipeMaterial

DATA_DIR = Path(__file__).resolve().parents[1] / "data"

# 来源类型归一化：站点原文 → 统一键
SOURCE_MAP = {"训练师": "trainer", "设计图": "design", "商人": "vendor", "掉落": "drop", "任务": "quest"}

# 专业图标（无限官方图标库 /tubiao/<name>.jpg，命名与 WoW 原版一致）
ICON_BASE = "https://wowforever.wclbox.com/tubiao"
PROFESSION_ICONS = {
    "blacksmithing": "trade_blacksmithing",
    "leatherworking": "trade_leatherworking",
    "tailoring": "trade_tailoring",
    "alchemy": "trade_alchemy",
    "enchanting": "trade_engraving",
    "engineering": "trade_engineering",
    "cooking": "inv_misc_food_15",
    "first-aid": "inv_misc_bandage_15",
    "mining": "trade_mining",
}


def profession_icon(key: str) -> str | None:
    name = PROFESSION_ICONS.get(key)
    return f"{ICON_BASE}/{name}.jpg" if name else None


def normalize_source(raw: str) -> str:
    return SOURCE_MAP.get(raw, raw)


def norm_recipe_name(name: str) -> str:
    """配方名规范化，用于匹配来源数据（去「公式：」前缀、括号后缀与空白）。"""
    s = re.sub(r"^.*?[：:]\s*", "", name) if re.match(r"^(公式|设计图|图样|结构图|配方|图纸)", name) else name
    s = re.sub(r"[（(].*?[)）]", "", s)
    return re.sub(r"\s+", "", s).strip()


def load_sources() -> dict[str, dict]:
    """读取 recipe_sources.json（不存在则返回空，来源列留空即可）。"""
    f = DATA_DIR / "recipe_sources.json"
    if not f.exists():
        print("提示：没有 data/recipe_sources.json，配方来源列留空（可运行 scrape_sources.py 生成）")
        return {}
    return json.loads(f.read_text(encoding="utf-8"))


def load_vendor_recipes() -> dict[str, dict]:
    """读取 vendor_recipes.json（贸易营地「商人青睐」配方清单）。"""
    f = DATA_DIR / "vendor_recipes.json"
    if not f.exists():
        print("提示：没有 data/vendor_recipes.json，贸易营地配方不标注（可运行 scrape_vendor_recipes.py 生成）")
        return {}
    return json.loads(f.read_text(encoding="utf-8"))


def lookup_vendor_favor(vendors: dict, prof_key: str, source_item_id: int | None) -> int | None:
    """查该图纸是否由贸易营地出售，返回需要的「商人青睐」点数。

    vendor_recipes.json 的 by_item 键是**图纸物品 ID**（如 251365 = 设计图：老兵的链甲腰带），
    不是成品 ID。
    """
    if not source_item_id:
        return None
    s = vendors.get(prof_key)
    if not s:
        return None
    entry = s.get("by_item", {}).get(str(source_item_id))
    return entry["favor"] if entry else None


def lookup_source(sources: dict, prof_key: str, item_id: int | None, name: str) -> str | None:
    """先按成品物品 ID 找，找不到再按配方名找（附魔成品没有物品 ID）。"""
    s = sources.get(prof_key)
    if not s:
        return None
    if item_id and str(item_id) in s.get("by_item", {}):
        return s["by_item"][str(item_id)] or None
    key = norm_recipe_name(name)
    return s.get("by_name", {}).get(key) or None


def seed(force: bool = False) -> None:
    init_db()
    prof_file = DATA_DIR / "professions.json"
    items_file = DATA_DIR / "items.json"
    if not prof_file.exists() or not items_file.exists():
        sys.exit(f"缺少种子文件：{prof_file} 或 {items_file}，请先运行 scraper")

    professions = json.loads(prof_file.read_text(encoding="utf-8"))["professions"]
    items = json.loads(items_file.read_text(encoding="utf-8"))["items"]

    db = SessionLocal()
    try:
        existing = db.execute(select(Profession)).scalars().all()
        if existing and not force:
            print(f"已有 {len(existing)} 个专业数据，跳过（--force 重建）")
            return
        if force:
            # 清空配方相关（保留服务器/价格/路线）
            db.execute(delete(RecipeMaterial))
            db.execute(delete(Recipe))
            db.execute(delete(MaterialSource))
            db.execute(delete(Profession))
            db.commit()
            print("已清空旧配方数据")

        # ---- 物品 ----
        item_objs = {}
        for it in items:
            obj = Item(
                id=it["id"],
                name=it["name"],
                name_en=it.get("name_en"),
                quality=it.get("quality", 0),
                item_level=it.get("item_level"),
                type=it.get("type"),
                class_id=it.get("class_id"),
                status=it.get("status"),
                icon=it.get("icon"),
                vendor_price=it.get("vendor_price", 0),
            )
            item_objs[it["id"]] = obj
        db.add_all(item_objs.values())
        db.flush()
        print(f"物品 {len(item_objs)} 条")

        # ---- 专业 / 配方 / 材料 / 来源 ----
        sources = load_sources()
        vendors = load_vendor_recipes()
        n_recipes = 0
        n_mats = 0
        n_src = 0
        n_vendor = 0
        for prof in professions:
            p = Profession(key=prof["key"], name=prof["name"], icon=profession_icon(prof["key"]))
            db.add(p)
            db.flush()
            for rec in prof["recipes"]:
                product = rec["product"]
                source = rec["source"]
                r = Recipe(
                    profession_id=p.id,
                    product_item_id=product["item_id"],
                    product_name=product["name"],
                    product_kind=product["kind"],
                    product_qty=product.get("yield_qty", 1),
                    is_new=bool(product.get("is_new")),
                    skill_orange=rec["skill"]["orange"],
                    skill_yellow=max(rec["skill"]["yellow"], rec["skill"]["orange"]),
                    skill_green=max(rec["skill"]["green"], rec["skill"]["yellow"]),
                    skill_gray=max(rec["skill"]["gray"], rec["skill"]["green"]),
                    source_type=normalize_source(source["type"]) if source["item_id"] is None else "design",
                    source_item_id=source["item_id"],
                    source_note=lookup_source(sources, prof["key"], product["item_id"], product["name"]),
                    vendor_favor=lookup_vendor_favor(vendors, prof["key"], source["item_id"]),
                )
                if r.source_note:
                    n_src += 1
                if r.vendor_favor:
                    n_vendor += 1
                db.add(r)
                db.flush()
                n_recipes += 1
                for mat in rec["materials"]:
                    db.add(
                        RecipeMaterial(recipe_id=r.id, item_id=mat["item_id"], qty=mat["qty"])
                    )
                    n_mats += 1
            for item_id_str, kind in prof.get("material_sources", {}).items():
                db.add(
                    MaterialSource(
                        profession_id=p.id, item_id=int(item_id_str), kind=kind
                    )
                )
        db.commit()
        print(f"专业 {len(professions)} 个，配方 {n_recipes} 个，材料行 {n_mats} 条")
        print(f"其中 {n_src} 个配方带来源说明（图纸从哪儿掉/哪个商人卖）")
        print(f"其中 {n_vendor} 个图纸来自贸易营地（需商人青睐购买）")
        print("种子加载完成")
    finally:
        db.close()


def fill_sources() -> None:
    """只把 recipe_sources.json 灌进已有数据库（不动价格/路线，无需重建配方）。"""
    init_db()
    sources = load_sources()
    if not sources:
        return
    db = SessionLocal()
    try:
        n = 0
        for p in db.execute(select(Profession)).scalars().all():
            s = sources.get(p.key)
            if not s:
                continue
            for r in db.execute(select(Recipe).where(Recipe.profession_id == p.id)).scalars().all():
                note = lookup_source(sources, p.key, r.product_item_id, r.product_name)
                if note and note != r.source_note:
                    r.source_note = note
                    n += 1
        db.commit()
        print(f"已写入/更新 {n} 条配方来源说明")
    finally:
        db.close()


def fill_vendor() -> None:
    """只把 vendor_recipes.json 的「商人青睐」标注灌进已有数据库。

    营地配方的来源说明要覆盖成营地文案（官方没在专业页来源列里写这一条，
    只有专题页才有），所以这里同时改写 source_note。
    """
    init_db()
    vendors = load_vendor_recipes()
    if not vendors:
        return
    db = SessionLocal()
    try:
        n = 0
        for p in db.execute(select(Profession)).scalars().all():
            v = vendors.get(p.key)
            if not v:
                continue
            camp_a = v.get("alliance", {})
            camp_h = v.get("horde", {})
            for r in db.execute(select(Recipe).where(Recipe.profession_id == p.id)).scalars().all():
                favor = lookup_vendor_favor(vendors, p.key, r.source_item_id)
                if favor is None:
                    continue
                r.vendor_favor = favor
                note = (
                    f"贸易营地 · {camp_a.get('camp', '艾泽拉斯贸易局')}（联盟 {camp_a.get('npc', '')}）"
                    f" / {camp_h.get('camp', '杜隆塔尔补给后勤部')}（部落 {camp_h.get('npc', '')}）"
                    f"，售价 {favor} 点商人青睐"
                )
                if r.source_note != note:
                    r.source_note = note
                n += 1
        db.commit()
        print(f"已标注 {n} 个贸易营地图纸（商人青睐价格）")
    finally:
        db.close()


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--force", action="store_true", help="清空重建配方数据")
    ap.add_argument("--sources-only", action="store_true", help="只灌配方来源，不重建")
    ap.add_argument("--vendor-only", action="store_true", help="只灌贸易营地标注，不重建")
    args = ap.parse_args()
    if args.vendor_only:
        fill_vendor()
    elif args.sources_only:
        fill_sources()
    else:
        seed(force=args.force)


if __name__ == "__main__":
    main()
