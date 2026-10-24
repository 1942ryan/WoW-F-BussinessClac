"""冲级路线计算引擎。

输入：服务器、专业、技能区间、价格口径（最新/中位数）、成品处置方式、
      屏蔽/确认的配方与物品。
输出：分阶段路线（每段：配方、次数、涨点概率、材料成本、成品收入）、
      材料汇总、警告与未参与计算的配方原因。

算法：事件驱动贪心。每个事件点（当前最佳配方的黄/绿/灰阈值、其他配方解锁点、
目标技能）重新评估「单位技能点净成本」最低的配方；用户确认采用的配方优先。
涨点概率采用 WoW 经典近似值（橙 100% / 黄 50% / 绿 25% / 灰 0%）。
"""

from __future__ import annotations

import math
import statistics
from dataclasses import dataclass, field
from datetime import datetime, timedelta

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ..models import Item, PriceRecord, Profession, Recipe, RecipeMaterial, MaterialSource
from ..schemas import CalcIn


# ---------- 工具 ----------


def fmt_copper(copper: int) -> str:
    """铜数格式化为 金/银/铜。"""
    if copper is None:
        return "-"
    neg = copper < 0
    c = abs(int(copper))
    gold, rem = divmod(c, 10000)
    silver, cop = divmod(rem, 100)
    parts = []
    if gold:
        parts.append(f"{gold}金")
    if silver:
        parts.append(f"{silver}银")
    if cop or not parts:
        parts.append(f"{cop}铜")
    return ("-" if neg else "") + "".join(parts)


def effective_prices(
    db: Session,
    server_id: int,
    mode: str,
    median_window_days: int = 0,
) -> dict[int, int]:
    """某服务器下每个物品的有效价格：latest=最新一条流水；median=中位数。"""
    if mode == "latest":
        # 可移植写法：每物品取最大 id（id 自增≈时间顺序）对应的流水
        latest_ids_sq = (
            select(
                PriceRecord.item_id.label("item_id"),
                func.max(PriceRecord.id).label("mid"),
            )
            .where(PriceRecord.server_id == server_id)
            .group_by(PriceRecord.item_id)
            .subquery()
        )
        rows = db.execute(
            select(PriceRecord.item_id, PriceRecord.unit_price)
            .join(
                latest_ids_sq,
                (PriceRecord.item_id == latest_ids_sq.c.item_id)
                & (PriceRecord.id == latest_ids_sq.c.mid),
            )
            .where(PriceRecord.server_id == server_id)
        ).all()
        return {item_id: price for item_id, price in rows}

    # median：取全部（或窗口内）流水按物品算中位数
    stmt = select(PriceRecord.item_id, PriceRecord.unit_price, PriceRecord.created_at).where(
        PriceRecord.server_id == server_id
    )
    if median_window_days > 0:
        since = datetime.utcnow() - timedelta(days=median_window_days)
        stmt = stmt.where(PriceRecord.created_at >= since)
    grouped: dict[int, list[int]] = {}
    for item_id, price, _ in db.execute(stmt).all():
        grouped.setdefault(item_id, []).append(price)
    return {k: int(round(statistics.median(v))) for k, v in grouped.items() if v}


# ---------- 内部结构 ----------


@dataclass
class MatLine:
    item_id: int
    name: str
    qty: int
    ah_price: int | None
    npc_price: int | None


@dataclass
class RecipeView:
    id: int
    product_item_id: int | None
    product_name: str
    product_qty: int
    is_new: bool
    orange: int
    yellow: int
    green: int
    gray: int
    source_type: str
    source_item_id: int | None
    mats: list[MatLine] = field(default_factory=list)
    mat_cost: int | None = None  # 每次材料成本（铜）
    revenue: int | None = None  # 每次成品收入（铜）
    net: int | None = None  # 每次净成本
    cost_per_point: float | None = None
    missing: list[str] = field(default_factory=list)  # 缺价格的材料名
    revenue_fallback: bool = False  # 拍卖行无价、按卖店价估算


def _band(recipe: RecipeView, skill: int) -> str:
    if skill < recipe.yellow:
        return "orange"
    if skill < recipe.green:
        return "yellow"
    return "green"


def _load_recipes(
    db: Session,
    profession: Profession,
    prices: dict[int, int],
    params: CalcIn,
) -> tuple[list[RecipeView], list[dict]]:
    """加载专业配方并计算每个配方的成本/收入；返回 (可用视图, 排除说明)。"""
    recipes = (
        db.execute(
            select(Recipe)
            .where(Recipe.profession_id == profession.id)
            .order_by(Recipe.skill_orange, Recipe.id)
        )
        .scalars()
        .unique()
        .all()
    )
    mat_rows = db.execute(
        select(RecipeMaterial).where(
            RecipeMaterial.recipe_id.in_([r.id for r in recipes])
        )
    ).scalars().all()
    mats_by_recipe: dict[int, list[RecipeMaterial]] = {}
    item_ids: set[int] = set()
    for m in mat_rows:
        mats_by_recipe.setdefault(m.recipe_id, []).append(m)
        item_ids.add(m.item_id)
    for r in recipes:
        if r.product_item_id:
            item_ids.add(r.product_item_id)

    items = {
        it.id: it
        for it in db.execute(select(Item).where(Item.id.in_(item_ids))).scalars().all()
    }
    # 商人出售标注（该专业购物清单）
    vendor_flag: dict[int, bool] = {}
    if mat_rows:
        ms_rows = db.execute(
            select(MaterialSource).where(
                MaterialSource.profession_id == profession.id,
                MaterialSource.item_id.in_(item_ids),
            )
        ).scalars().all()
        vendor_flag = {ms.item_id: ms.kind == "vendor" for ms in ms_rows}

    blocked_recipes = set(params.blocked_recipe_ids)
    blocked_items = set(params.blocked_item_ids)
    confirmed = set(params.confirmed_recipe_ids)

    views: list[RecipeView] = []
    excluded: list[dict] = []

    for r in recipes:
        # 技能档钳制（个别配方源数据黄<橙等异常）
        orange = r.skill_orange
        yellow = max(r.skill_yellow, orange)
        green = max(r.skill_green, yellow)
        gray = max(r.skill_gray, green)
        view = RecipeView(
            id=r.id,
            product_item_id=r.product_item_id,
            product_name=r.product_name,
            product_qty=r.product_qty,
            is_new=r.is_new,
            orange=orange,
            yellow=yellow,
            green=green,
            gray=gray,
            source_type=r.source_type,
            source_item_id=r.source_item_id,
        )

        # 排除逻辑
        if r.id in blocked_recipes:
            excluded.append({"recipe_id": r.id, "name": r.product_name, "reason": "用户屏蔽"})
            continue
        if not params.include_designs and r.source_type == "design":
            excluded.append(
                {"recipe_id": r.id, "name": r.product_name, "reason": "设计图配方未启用"}
            )
            continue
        if r.product_item_id and r.product_item_id in blocked_items:
            excluded.append({"recipe_id": r.id, "name": r.product_name, "reason": "成品被屏蔽"})
            continue

        # 材料成本
        missing: list[str] = []
        mat_cost = 0
        for m in mats_by_recipe.get(r.id, []):
            item = items.get(m.item_id)
            name = item.name if item else f"物品{m.item_id}"
            if m.item_id in blocked_items:
                missing.append(f"{name}(已屏蔽)")
                continue
            ah = prices.get(m.item_id)
            npc = items[m.item_id].vendor_price if vendor_flag.get(m.item_id) else None
            unit = None
            if ah is not None and npc is not None:
                unit = min(ah, npc)
            elif ah is not None:
                unit = ah
            elif npc is not None:
                unit = npc
            if unit is None:
                missing.append(name)
                continue
            view.mats.append(
                MatLine(
                    item_id=m.item_id,
                    name=name,
                    qty=m.qty,
                    ah_price=ah,
                    npc_price=npc,
                )
            )
            mat_cost += unit * m.qty

        if missing:
            view.missing = missing
            excluded.append(
                {
                    "recipe_id": r.id,
                    "name": r.product_name,
                    "reason": "材料无价格: " + ", ".join(missing),
                }
            )
            continue
        view.mat_cost = mat_cost

        # 成品收入
        revenue = 0
        if r.product_item_id:
            if params.product_disposition == "sell_ah":
                ah = prices.get(r.product_item_id)
                if ah is not None:
                    revenue = ah * r.product_qty
                else:
                    vp = items[r.product_item_id].vendor_price
                    revenue = vp * r.product_qty
                    view.revenue_fallback = vp > 0
            elif params.product_disposition == "sell_npc":
                vp = items[r.product_item_id].vendor_price
                revenue = vp * r.product_qty
            # self_use → 0
        view.revenue = revenue
        view.net = mat_cost - revenue
        views.append(view)

    return views, excluded


def calc_route(db: Session, params: CalcIn, settings) -> dict:
    profession = db.execute(
        select(Profession).where(Profession.key == params.profession_key)
    ).scalar_one_or_none()
    if profession is None:
        raise ValueError(f"专业不存在: {params.profession_key}")
    if params.to_skill <= params.from_skill:
        raise ValueError("目标技能必须大于当前技能")

    prices = effective_prices(
        db, params.server_id, params.price_mode, settings.median_window_days
    )
    views, excluded = _load_recipes(db, profession, prices, params)

    probs = {
        "orange": settings.prob_orange,
        "yellow": settings.prob_yellow,
        "green": settings.prob_green,
    }

    # 单位技能点净成本（用于贪心排序）
    for v in views:
        v.cost_per_point = None  # 依赖当前技能档，运行时计算

    confirmed = set(params.confirmed_recipe_ids)
    steps: list[dict] = []
    mat_totals: dict[int, dict] = {}
    warnings: list[str] = []
    total_crafts = 0
    total_mat = 0
    total_rev = 0
    skill = params.from_skill

    def unit_cost(v: RecipeView, s: int) -> float:
        band = _band(v, s)
        prob = probs[band]
        if prob <= 0:
            return float("inf")
        return v.net / prob

    while skill < params.to_skill:
        available = [v for v in views if v.orange <= skill < v.gray]
        if not available:
            warnings.append(
                f"技能 {skill} 起无可用配方"
                "（材料无拍卖行/NPC 价格，或可用配方均被屏蔽）"
            )
            break
        conf_pool = [v for v in available if v.id in confirmed]
        pool = conf_pool if conf_pool else available
        best = min(pool, key=lambda v: (unit_cost(v, skill), v.gray, v.id))

        # 下一事件点：本配方档位阈值 / 其他配方解锁点 / 目标
        events = [t for t in (best.yellow, best.green, best.gray) if t > skill]
        events.extend(v.orange for v in views if v.orange > skill)
        seg_to = min([*events, params.to_skill])

        band = _band(best, skill)
        prob = probs[band]
        points = seg_to - skill
        crafts = max(1, math.ceil(points / prob))

        step_net = best.net * crafts
        step_mat = best.mat_cost * crafts
        step_rev = best.revenue * crafts
        steps.append(
            {
                "skill_from": skill,
                "skill_to": seg_to,
                "recipe_id": best.id,
                "recipe_name": best.product_name,
                "product_item_id": best.product_item_id,
                "crafts": crafts,
                "prob": prob,
                "band": band,
                "mat_cost": step_mat,
                "revenue": step_rev,
                "net": step_net,
                "confirmed": best.id in confirmed,
                "source_type": best.source_type,
            }
        )
        if best.revenue_fallback:
            warnings.append(
                f"「{best.product_name}」拍卖行暂无价格，收入按 NPC 卖店价估算"
            )
        for m in best.mats:
            agg = mat_totals.setdefault(
                m.item_id,
                {"item_id": m.item_id, "name": m.name, "qty": 0},
            )
            agg["qty"] += m.qty * crafts

        total_crafts += crafts
        total_mat += step_mat
        total_rev += step_rev
        skill = seg_to

    # 合并相邻的「同配方 + 同档位」步骤（事件点切分过细，合并后更易读）
    merged_steps: list[dict] = []
    for st in steps:
        last = merged_steps[-1] if merged_steps else None
        if (
            last
            and last["recipe_id"] == st["recipe_id"]
            and last["band"] == st["band"]
            and last["skill_to"] == st["skill_from"]
        ):
            last["skill_to"] = st["skill_to"]
            last["crafts"] += st["crafts"]
            last["mat_cost"] += st["mat_cost"]
            last["revenue"] += st["revenue"]
            last["net"] += st["net"]
        else:
            merged_steps.append(st)
    steps = merged_steps

    # 材料单价与来源
    materials = []
    for item_id, agg in mat_totals.items():
        ah = prices.get(item_id)
        # NPC 价：从配方行反推较麻烦，这里直接查一次
        npc = None
        ms_kind = db.execute(
            select(MaterialSource.kind).where(
                MaterialSource.profession_id == profession.id,
                MaterialSource.item_id == item_id,
            )
        ).scalar_one_or_none()
        if ms_kind == "vendor":
            item = db.get(Item, item_id)
            npc = item.vendor_price if item else None
        unit = None
        source = None
        if ah is not None and npc is not None:
            unit, source = (ah, "ah") if ah <= npc else (npc, "npc")
        elif ah is not None:
            unit, source = ah, "ah"
        elif npc is not None:
            unit, source = npc, "npc"
        materials.append(
            {
                "item_id": item_id,
                "name": agg["name"],
                "qty": agg["qty"],
                "unit_price": unit,
                "price_source": source,
                "cost": unit * agg["qty"] if unit is not None else None,
            }
        )
    materials.sort(key=lambda m: (m["cost"] is None, -(m["cost"] or 0)))

    net_total = total_mat - total_rev
    return {
        "profession": {"key": profession.key, "name": profession.name},
        "server": {"id": params.server_id},
        "params": params.model_dump(),
        "steps": steps,
        "totals": {
            "crafts": total_crafts,
            "mat_cost": total_mat,
            "revenue": total_rev,
            "net": net_total,
            "net_display": fmt_copper(net_total),
        },
        "materials": materials,
        "warnings": warnings,
        "excluded": excluded,
    }
