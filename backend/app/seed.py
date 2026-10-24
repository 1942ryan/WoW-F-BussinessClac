"""种子数据加载：professions.json + items.json → 数据库。

用法：
    python -m app.seed            # 仅当专业表为空时加载
    python -m app.seed --force    # 清空重建配方相关数据
"""

from __future__ import annotations

import argparse
import json
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
        n_recipes = 0
        n_mats = 0
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
                )
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
        print("种子加载完成")
    finally:
        db.close()


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--force", action="store_true", help="清空重建配方数据")
    args = ap.parse_args()
    seed(force=args.force)


if __name__ == "__main__":
    main()
