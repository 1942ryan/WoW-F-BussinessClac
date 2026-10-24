"""专业与配方浏览路由。"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ..config import get_settings
from ..database import get_db
from ..models import Item, MaterialSource, Profession, Recipe, RecipeMaterial
from ..schemas import MaterialOut, ProfessionOut, RecipeOut
from ..services.calc import effective_prices

router = APIRouter(prefix="/professions", tags=["professions"])


@router.get("", response_model=list[ProfessionOut])
def list_professions(db: Session = Depends(get_db)) -> list[ProfessionOut]:
    profs = db.execute(select(Profession).order_by(Profession.id)).scalars().all()
    counts = dict(
        db.execute(select(Recipe.profession_id, func.count()).group_by(Recipe.profession_id)).all()
    )
    max_skills = dict(
        db.execute(select(Recipe.profession_id, func.max(Recipe.skill_gray)).group_by(Recipe.profession_id)).all()
    )
    return [
        ProfessionOut(
            id=p.id,
            key=p.key,
            name=p.name,
            recipe_count=counts.get(p.id, 0),
            max_skill=max_skills.get(p.id) or 0,
        )
        for p in profs
    ]


@router.get("/{key}/recipes", response_model=list[RecipeOut])
def list_recipes(
    key: str,
    server_id: int | None = Query(default=None, description="提供后附带价格与成本"),
    price_mode: str = Query(default="latest", pattern="^(latest|median)$"),
    disposition: str = Query(default="sell_ah", pattern="^(sell_ah|sell_npc|self_use)$"),
    from_skill: int | None = Query(default=None, ge=0),
    to_skill: int | None = Query(default=None, ge=0),
    db: Session = Depends(get_db),
) -> list[RecipeOut]:
    prof = db.execute(select(Profession).where(Profession.key == key)).scalar_one_or_none()
    if prof is None:
        raise HTTPException(404, f"专业不存在: {key}")

    prices: dict[int, int] = {}
    if server_id:
        prices = effective_prices(db, server_id, price_mode, get_settings().median_window_days)

    recipes = (
        db.execute(
            select(Recipe)
            .where(Recipe.profession_id == prof.id)
            .order_by(Recipe.skill_orange, Recipe.id)
        )
        .scalars()
        .unique()
        .all()
    )
    mat_rows = (
        db.execute(
            select(RecipeMaterial).where(RecipeMaterial.recipe_id.in_([r.id for r in recipes]))
        )
        .scalars()
        .all()
    )
    mats_by_recipe: dict[int, list[RecipeMaterial]] = {}
    item_ids: set[int] = set()
    for m in mat_rows:
        mats_by_recipe.setdefault(m.recipe_id, []).append(m)
        item_ids.add(m.item_id)
    for r in recipes:
        if r.product_item_id:
            item_ids.add(r.product_item_id)
        if r.source_item_id:
            item_ids.add(r.source_item_id)
    items = {i.id: i for i in db.execute(select(Item).where(Item.id.in_(item_ids))).scalars().all()}
    vendor_flags = {
        ms.item_id: ms.kind == "vendor"
        for ms in db.execute(
            select(MaterialSource).where(
                MaterialSource.profession_id == prof.id, MaterialSource.item_id.in_(item_ids)
            )
        )
        .scalars()
        .all()
    }

    out: list[RecipeOut] = []
    for r in recipes:
        if from_skill is not None and r.skill_gray <= from_skill:
            continue
        if to_skill is not None and r.skill_orange > to_skill:
            continue
        materials: list[MaterialOut] = []
        mat_cost = 0
        price_ok = True
        for m in mats_by_recipe.get(r.id, []):
            item = items.get(m.item_id)
            ah = prices.get(m.item_id)
            npc = item.vendor_price if (item and vendor_flags.get(m.item_id)) else None
            unit, source = None, None
            if ah is not None and npc is not None:
                unit, source = (ah, "ah") if ah <= npc else (npc, "npc")
            elif ah is not None:
                unit, source = ah, "ah"
            elif npc is not None:
                unit, source = npc, "npc"
            if unit is None:
                price_ok = False
            else:
                mat_cost += unit * m.qty
            materials.append(
                MaterialOut(
                    item_id=m.item_id,
                    name=item.name if item else f"物品{m.item_id}",
                    qty=m.qty,
                    unit_price=unit,
                    price_source=source,
                    line_cost=unit * m.qty if unit is not None else None,
                )
            )
        revenue = None
        if price_ok and r.product_item_id:
            if disposition == "sell_ah":
                revenue = (prices.get(r.product_item_id) or items[r.product_item_id].vendor_price) * r.product_qty
            elif disposition == "sell_npc":
                revenue = items[r.product_item_id].vendor_price * r.product_qty
            else:
                revenue = 0
        out.append(
            RecipeOut(
                id=r.id,
                product_item_id=r.product_item_id,
                product_name=r.product_name,
                product_kind=r.product_kind,
                product_qty=r.product_qty,
                is_new=r.is_new,
                skill_orange=r.skill_orange,
                skill_yellow=r.skill_yellow,
                skill_green=r.skill_green,
                skill_gray=r.skill_gray,
                source_type=r.source_type,
                source_item_id=r.source_item_id,
                source_name=items[r.source_item_id].name if r.source_item_id and r.source_item_id in items else None,
                materials=materials,
                mat_cost=mat_cost if price_ok else None,
                revenue=revenue,
                net_cost=(mat_cost - revenue) if (price_ok and revenue is not None) else None,
            )
        )
    return out
