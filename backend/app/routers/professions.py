"""专业与配方浏览路由。"""

from __future__ import annotations

import json
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ..config import get_settings
from ..database import get_db
from ..models import (
    FACTION_ALLIANCE,
    FACTION_HORDE,
    Item,
    MaterialSource,
    Profession,
    Recipe,
    RecipeMaterial,
    Server,
)
from ..schemas import (
    MaterialOut,
    ProfessionOut,
    RecipeOut,
    VendorCampOut,
    WatchlistItemOut,
    WatchlistOut,
)
from ..services.calc import ah_net_of, effective_prices, fmt_copper, is_limited_vendor

router = APIRouter(prefix="/professions", tags=["professions"])

# 贸易营地（商人青睐）信息：来自 data/vendor_recipes.json，抓自官方专题页 /shangren
_VENDOR_CACHE: dict[str, dict] | None = None


def _vendor_data() -> dict[str, dict]:
    global _VENDOR_CACHE
    if _VENDOR_CACHE is None:
        f = Path(__file__).resolve().parents[2] / "data" / "vendor_recipes.json"
        try:
            _VENDOR_CACHE = json.loads(f.read_text(encoding="utf-8")) if f.exists() else {}
        except (OSError, ValueError):
            _VENDOR_CACHE = {}
    return _VENDOR_CACHE


def _camp_for(vendor: dict, faction: str) -> VendorCampOut | None:
    """按阵营取对应营地。both/未知 → 联盟（列表页默认展示联盟侧）。"""
    side = faction if faction in (FACTION_ALLIANCE, FACTION_HORDE) else FACTION_ALLIANCE
    c = vendor.get(side)
    if not c:
        return None
    return VendorCampOut(
        camp=c.get("camp", ""),
        npc=c.get("npc", ""),
        zone=c.get("zone", ""),
        coord=c.get("coord", ""),
        crate_npc=c.get("crate_npc", ""),
        side=side,
    )


@router.get("/{key}/watchlist", response_model=WatchlistOut)
def profession_watchlist(
    key: str,
    from_skill: int | None = Query(default=None, ge=0),
    to_skill: int | None = Query(default=None, ge=0),
    db: Session = Depends(get_db),
) -> WatchlistOut:
    """导出 AUC 关注清单：该专业（可选技能区间）全部配方涉及的物品。

    输出文本格式为「清单名^物品1^物品2^…」，可在游戏内 AUC 的关注清单
    导入里直接粘贴，随后按清单导出价格文本，回本页导入。
    """
    prof = db.execute(select(Profession).where(Profession.key == key)).scalar_one_or_none()
    if prof is None:
        raise HTTPException(404, f"专业不存在: {key}")

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
    if from_skill is not None:
        recipes = [r for r in recipes if r.skill_gray > from_skill]
    if to_skill is not None:
        recipes = [r for r in recipes if r.skill_orange <= to_skill]

    mat_rows = (
        db.execute(
            select(RecipeMaterial).where(RecipeMaterial.recipe_id.in_([r.id for r in recipes]))
        )
        .scalars()
        .all()
    )
    kinds: dict[int, str] = {}
    for m in mat_rows:
        kinds.setdefault(m.item_id, "material")
    for r in recipes:
        if r.product_item_id:
            kinds.setdefault(r.product_item_id, "product")
        if r.source_item_id:
            kinds.setdefault(r.source_item_id, "design")

    items = {i.id: i for i in db.execute(select(Item).where(Item.id.in_(kinds))).scalars().all()}
    entries = sorted(
        (
            {"item_id": i, "name": items[i].name, "icon": items[i].icon, "kind": k}
            for i, k in kinds.items()
            if i in items
        ),
        key=lambda e: e["name"],
    )
    text = "^".join([prof.name, *(e["name"] for e in entries)])
    return WatchlistOut(
        profession={"key": prof.key, "name": prof.name},
        list_name=prof.name,
        count=len(entries),
        items=[WatchlistItemOut(**e) for e in entries],
        text=text,
    )


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
            icon=p.icon,
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
    recipe_dispositions: str | None = Query(default=None, description="单配方处置覆盖 JSON"),
    from_skill: int | None = Query(default=None, ge=0),
    to_skill: int | None = Query(default=None, ge=0),
    db: Session = Depends(get_db),
) -> list[RecipeOut]:
    prof = db.execute(select(Profession).where(Profession.key == key)).scalar_one_or_none()
    if prof is None:
        raise HTTPException(404, f"专业不存在: {key}")

    disp_overrides: dict[int, str] = {}
    if recipe_dispositions:
        try:
            raw = json.loads(recipe_dispositions)
            disp_overrides = {int(k): v for k, v in raw.items()}
        except (ValueError, TypeError):
            raise HTTPException(400, "recipe_dispositions 需为 JSON 对象")

    prices: dict[int, int] = {}
    faction = "both"
    settings = get_settings()
    ah_cut_rate = float(getattr(settings, "ah_cut_rate", 0.05) or 0.0)
    if server_id:
        prices = effective_prices(db, server_id, price_mode, settings.median_window_days)
        srv = db.get(Server, server_id)
        if srv:
            faction = srv.faction or "both"

    vendor = _vendor_data().get(key)
    camp = _camp_for(vendor, faction) if vendor else None

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
            limited = is_limited_vendor(item)
            npc = (
                item.vendor_price
                if (item and vendor_flags.get(m.item_id) and not limited)
                else None
            )
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
                    icon=item.icon if item else None,
                    qty=m.qty,
                    unit_price=unit,
                    price_source=source,
                    line_cost=unit * m.qty if unit is not None else None,
                )
            )
        revenue = None
        disp = disp_overrides.get(r.id) or disposition
        product_npc_price: int | None = None
        product_ah_price: int | None = None
        if price_ok and r.product_item_id:
            prod_item = items[r.product_item_id]
            product_npc_price = (prod_item.vendor_price or 0) * r.product_qty
            ah_price = prices.get(r.product_item_id)
            product_ah_price = ah_price * r.product_qty if ah_price is not None else None
            if disp == "sell_ah":
                # 与路线计算同口径：拍卖行收入按扣完 5% 手续费的到手价
                revenue = (
                    ah_net_of(product_ah_price, ah_cut_rate)
                    if product_ah_price is not None
                    else product_npc_price
                )
            elif disp == "sell_npc":
                revenue = product_npc_price
            else:
                revenue = 0
        # 来源详情（悬停展示）：训练师标明可学等级；设计图标明图纸名与拍卖行/卖店价，
        # 让用户知道这张图纸到底能不能买到、多少钱
        source_detail: str | None = None
        if r.source_type == "trainer":
            source_detail = f"训练师教授\n技能 {r.skill_orange} 级可直接学习"
            if r.source_note and r.source_note != "训练师":
                source_detail += f"\n{r.source_note}"
        else:
            src_item = items.get(r.source_item_id) if r.source_item_id else None
            src_name = (
                src_item.name
                if src_item
                else (f"物品{r.source_item_id}" if r.source_item_id else "未知图纸")
            )
            # 图纸物品名本身常带「设计图：」前缀，避免拼成「设计图：设计图：xxx」
            head = src_name if src_name.startswith("设计图") else f"设计图：{src_name}"
            lines = [head]
            if server_id:
                ah = prices.get(r.source_item_id) if r.source_item_id else None
                if ah is not None:
                    lines.append(f"拍卖行：{fmt_copper(ah)}")
                elif r.vendor_favor:
                    # 营地图纸在拍卖行买不到，只能去营地换青睐
                    lines.append("拍卖行：无报价（营地图纸买不到，只能去营地换青睐）")
                else:
                    lines.append("拍卖行：暂无报价（可能靠掉落或向玩家收购）")
                if src_item and src_item.vendor_price:
                    lines.append(f"卖店：{fmt_copper(src_item.vendor_price)}")
            # 图纸出处：哪个商人卖 / 哪儿掉 / 开什么箱子（官方库没收录时留空）
            if r.source_note:
                lines.append(f"出处：{r.source_note}")
            # 贸易营地专属图纸：需要「商人青睐」而不是声望
            if r.vendor_favor and camp:
                lines.append(
                    f"商人青睐：{r.vendor_favor} 点"
                    f"（{camp.camp} · {camp.npc}，{camp.zone} {camp.coord}）"
                )
                lines.append(
                    f"获得青睐：上交装满的板条箱给{camp.crate_npc or '营地NPC'}"
                    f"（每箱 5–20 点，箱子和材料要自己准备）"
                )
                lines.append("提示：营地配方没有声望要求，两阵营配方和价格完全相同")
            source_detail = "\n".join(lines)

        out.append(
            RecipeOut(
                id=r.id,
                product_item_id=r.product_item_id,
                product_name=r.product_name,
                product_icon=items[r.product_item_id].icon if r.product_item_id and r.product_item_id in items else None,
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
                product_npc_price=product_npc_price,
                product_ah_price=product_ah_price,
                # 卖拍卖行但查不到 AH 价 → 收入按卖店价估算（冷门信号，由用户决定是否屏蔽）
                revenue_fallback=(
                    disp == "sell_ah"
                    and product_ah_price is None
                    and (product_npc_price or 0) > 0
                ),
                source_detail=source_detail,
                vendor_favor=r.vendor_favor,
                vendor_camp=camp if r.vendor_favor else None,
            )
        )
    return out
