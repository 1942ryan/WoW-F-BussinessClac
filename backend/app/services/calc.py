"""冲级路线计算引擎。

输入：服务器、专业、技能区间、价格口径（最新/中位数）、成品处置方式、
      屏蔽/确认的配方与物品、涨点几率模型。
输出：分阶段路线（每段：配方、次数、涨点概率、材料成本、成品收入）、
      材料汇总、警告与未参与计算的配方原因。

算法：事件驱动贪心。每个事件点（当前最佳配方的黄/绿/灰阈值、其他配方解锁点、
目标技能）重新评估「单位技能点净成本」最低的配方；用户确认采用的配方优先
（有次数上限，用尽后按长 CD 处理不再参与）。

涨点几率（WoW 经典客户端机制，WowWiki 存档 + SkillUpProbability 插件实证）：
- 橙档（当前技能 < 黄档）：100%
- 黄/绿档：几率 = (灰档 - 当前技能) / (灰档 - 黄档)
  → 刚变黄时仍接近 100%，到绿档时 50%，向灰档衰减至 0
- 灰档：0%
私服若自定义了几率，可在界面切到「固定档位」手动填写橙/黄/绿几率。
"""

from __future__ import annotations

import math
import statistics
from dataclasses import dataclass, field
from datetime import datetime, timedelta

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ..models import (
    FACTION_BOTH,
    Item,
    PriceRecord,
    Profession,
    Recipe,
    RecipeMaterial,
    MaterialSource,
    Server,
)
from ..schemas import CalcIn


# ---------- NPC 限量材料 ----------

# NPC 只卖少量、冲级不能依靠的材料类型（小写）。草药是典型：草药学训练师
# 旁边虽然能买到几棵，但存量极少，价格应按拍卖行计。
LIMITED_VENDOR_TYPES = {"herb"}
# 额外手工标注的限量物品 ID（私服若有其他限量货，按 ID 加进来即可）
MANUAL_LIMITED_ITEM_IDS: set[int] = set()


def is_limited_vendor(item: Item | None) -> bool:
    """该物品是否为「NPC 限量供应」（不采用 NPC 卖价，只认拍卖行）。"""
    if item is None:
        return False
    if item.id in MANUAL_LIMITED_ITEM_IDS:
        return True
    return (item.type or "").strip().lower() in LIMITED_VENDOR_TYPES


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
    """某服务器下每个物品的有效价格：latest=最新一条流水；median=中位数。

    联盟/部落价格隔离：服务器标记了阵营（非 both）时，只取该阵营导入的流水
    （both 的旧数据作为公共底价保留可见）。
    """
    server = db.get(Server, server_id)
    faction = server.faction if server else FACTION_BOTH

    def _scope(stmt):
        stmt = stmt.where(PriceRecord.server_id == server_id)
        if faction != FACTION_BOTH:
            stmt = stmt.where(
                (PriceRecord.faction == faction) | (PriceRecord.faction == FACTION_BOTH)
            )
        return stmt

    if mode == "latest":
        # 可移植写法：每物品取最大 id（id 自增≈时间顺序）对应的流水
        latest_ids_sq = (
            select(
                PriceRecord.item_id.label("item_id"),
                func.max(PriceRecord.id).label("mid"),
            )
            .where(PriceRecord.server_id == server_id)
            .group_by(PriceRecord.item_id)
        )
        if faction != FACTION_BOTH:
            latest_ids_sq = latest_ids_sq.where(
                (PriceRecord.faction == faction) | (PriceRecord.faction == FACTION_BOTH)
            )
        latest_ids_sq = latest_ids_sq.subquery()
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
    stmt = select(PriceRecord.item_id, PriceRecord.unit_price, PriceRecord.created_at)
    stmt = _scope(stmt)
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
    icon: str | None
    qty: int
    ah_price: int | None
    npc_price: int | None
    npc_limited: bool = False  # NPC 限量（如草药），不采用 NPC 价


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
    product_icon: str | None = None  # 成品图标 URL
    mats: list[MatLine] = field(default_factory=list)
    mat_cost: int | None = None  # 每次材料成本（铜）
    revenue: int | None = None  # 每次成品收入（铜）
    net: int | None = None  # 每次净成本
    cost_per_point: float | None = None
    missing: list[str] = field(default_factory=list)  # 缺价格的材料名
    revenue_fallback: bool = False  # 拍卖行无价、按卖店价估算（仅记录，不对外提示）
    disposition: str = "sell_ah"  # 本配方产物处置（全局或单配方覆盖）
    # 设计图配方：图纸一次性成本（学会即消耗，不随制作次数增加）
    design_cost: int = 0
    design_name: str | None = None
    design_icon: str | None = None


def _band(recipe: RecipeView, skill: int) -> str:
    if skill < recipe.yellow:
        return "orange"
    if skill < recipe.green:
        return "yellow"
    return "green"


def _chance(v: RecipeView, skill: float, mode: str, probs: dict[str, float]) -> float:
    """当前技能下制作该配方的涨点几率。

    formula：WoW 经典客户端公式 (灰档-当前)/(灰档-黄档)，橙档 100%。
    fixed：按档位固定几率（用户自填，适用于自定义几率的私服）。
    """
    if mode == "fixed":
        return probs[_band(v, skill)]
    if skill < v.yellow:
        return 1.0
    if skill >= v.gray:
        return 0.0
    span = v.gray - v.yellow
    if span <= 0:  # 源数据异常（黄≥灰），按橙档处理
        return 1.0
    return max(0.0, min(1.0, (v.gray - skill) / span))


def _expected_crafts(v: RecipeView, s: float, target: float, mode: str, probs: dict[str, float]) -> float:
    """从技能 s 到 target 的期望制作次数（每点按 1/几率 累加）。"""
    crafts = 0.0
    cur = float(s)
    guard = 0
    while cur < target - 1e-9:
        p = _chance(v, cur, mode, probs)
        if p <= 0:
            return float("inf")
        crafts += 1.0 / p
        cur += 1.0
        guard += 1
        if guard > 400:  # 防御：区间不可能超过 375
            return float("inf")
    return crafts


def _points_after_crafts(
    v: RecipeView, s: float, n: float, mode: str, probs: dict[str, float], cap_to: float
) -> float:
    """制作 n 次后的期望涨点数（用于确认次数用尽、段未走完的情况）。"""
    cur = float(s)
    gained = 0.0
    left = float(n)
    while left >= 1.0 and cur < cap_to - 1e-9:
        p = _chance(v, cur, mode, probs)
        if p <= 0:
            break
        step = min(p, cap_to - cur)
        gained += step
        cur += step
        left -= 1.0
    return min(gained, cap_to - s)


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
        if r.source_item_id:
            item_ids.add(r.source_item_id)

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
    disp_overrides = dict(params.recipe_dispositions or {})

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
            product_icon=(items[r.product_item_id].icon if r.product_item_id in items else None),
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
        if r.source_type == "design" and r.source_item_id in blocked_items:
            excluded.append(
                {"recipe_id": r.id, "name": r.product_name, "reason": "设计图物品被屏蔽"}
            )
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
            limited = is_limited_vendor(item)
            npc = item.vendor_price if (vendor_flag.get(m.item_id) and not limited) else None
            unit = None
            if ah is not None and npc is not None:
                unit = min(ah, npc)
            elif ah is not None:
                unit = ah
            elif npc is not None:
                unit = npc
            if unit is None:
                if limited and ah is None:
                    missing.append(f"{name}(NPC限量,需拍卖行价格)")
                else:
                    missing.append(name)
                continue
            view.mats.append(
                MatLine(
                    item_id=m.item_id,
                    name=name,
                    icon=item.icon if item else None,
                    qty=m.qty,
                    ah_price=ah,
                    npc_price=npc,
                    npc_limited=limited,
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

        # 成品收入（处置方式：全局默认，单配方可覆盖）
        disposition = disp_overrides.get(r.id) or params.product_disposition
        view.disposition = disposition
        revenue = 0
        if r.product_item_id:
            if disposition == "sell_ah":
                ah = prices.get(r.product_item_id)
                if ah is not None:
                    revenue = ah * r.product_qty
                else:
                    vp = items[r.product_item_id].vendor_price
                    revenue = vp * r.product_qty
                    view.revenue_fallback = vp > 0
            elif disposition == "sell_npc":
                vp = items[r.product_item_id].vendor_price
                revenue = vp * r.product_qty
            # self_use → 0
        view.revenue = revenue
        view.net = mat_cost - revenue

        # 设计图成本（一次性，学会配方即消耗）
        if r.source_type == "design" and r.source_item_id:
            design_item = items.get(r.source_item_id)
            view.design_name = design_item.name if design_item else f"物品{r.source_item_id}"
            view.design_icon = design_item.icon if design_item else None
            if params.design_cost == "ah":
                dp = prices.get(r.source_item_id)
                if dp is not None:
                    view.design_cost = dp
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
        "orange": params.prob_orange if params.prob_orange is not None else settings.prob_orange,
        "yellow": params.prob_yellow if params.prob_yellow is not None else settings.prob_yellow,
        "green": params.prob_green if params.prob_green is not None else settings.prob_green,
    }

    # 确认配法的剩余制作次数（浮点：公式模式下期望次数可能是小数）
    remaining: dict[int, float] = {}
    for rid in params.confirmed_recipe_ids:
        cnt = (params.confirmed_counts or {}).get(rid, 1)
        if cnt >= 1:  # 次数 ≤0 视为未确认（不优先、不限额）
            remaining[rid] = float(cnt)
    exhausted: set[int] = set()  # 确认次数已用完（按 CD 限制退出计算）
    skip: set[int] = set()  # 当前区间内不可行（几率 0 等）的配方

    design_paid: set[int] = set()  # 已计入一次性图纸成本的配方
    steps: list[dict] = []
    mat_totals: dict[int, dict] = {}
    warnings: list[str] = []
    total_crafts = 0.0
    total_mat = 0
    total_rev = 0
    skill = float(params.from_skill)

    def chance(v: RecipeView, s: float) -> float:
        return _chance(v, s, params.prob_mode, probs)

    def unit_cost(v: RecipeView, s: float) -> float:
        p = chance(v, s)
        if p <= 0:
            return float("inf")
        return v.net / p

    while skill < params.to_skill - 1e-9:
        available = [
            v
            for v in views
            if v.orange <= skill < v.gray and v.id not in exhausted and v.id not in skip
        ]
        if not available:
            warnings.append(
                f"技能 {int(round(skill))} 起无可用配方"
                "（材料无拍卖行/NPC 价格，或可用配方均被屏蔽/次数用尽）"
            )
            break
        conf_pool = [v for v in available if v.id in remaining and remaining[v.id] >= 0.5]
        pool = conf_pool if conf_pool else available
        best = min(pool, key=lambda v: (unit_cost(v, skill), v.gray, v.id))

        # 下一事件点：本配方档位阈值 / 其他配方解锁点 / 目标
        events = [t for t in (best.yellow, best.green, best.gray) if t > skill]
        events.extend(v.orange for v in views if v.orange > skill)
        seg_to = min([*events, params.to_skill])

        band = _band(best, skill)
        prob = chance(best, skill)
        points = seg_to - skill

        # 期望制作次数：fixed=按档位恒定几率；formula=逐点 1/几率 累加
        if params.prob_mode == "fixed":
            crafts = math.ceil(points / prob) if prob > 0 else float("inf")
        else:
            crafts = _expected_crafts(best, skill, seg_to, params.prob_mode, probs)
        if not math.isfinite(crafts):
            # 该配方在此区间几率过低/为 0，跳过重选
            skip.add(best.id)
            continue

        # 确认配方次数上限（长 CD 配方：一个查询周期内只能做 N 次）
        capped = False
        if best.id in remaining:
            cap = remaining[best.id]
            if cap < crafts:
                crafts = cap
                capped = True

        if crafts < 1e-9:
            exhausted.add(best.id)
            excluded.append(
                {
                    "recipe_id": best.id,
                    "name": best.product_name,
                    "reason": "确认次数已用完",
                }
            )
            continue

        # 段末几率（公式模式下随技能衰减；fixed 下与段首相同）
        if params.prob_mode == "fixed":
            prob_end = prob
        else:
            prob_end = chance(best, max(skill, seg_to - 1.0))

        step_net = best.net * crafts
        step_mat = best.mat_cost * crafts
        step_rev = best.revenue * crafts

        # 设计图一次性成本（同一配方只计一次）
        step_design_cost = 0
        step_design_name: str | None = None
        if best.source_type == "design" and best.id not in design_paid:
            design_paid.add(best.id)
            step_design_cost = best.design_cost
            step_design_name = best.design_name
            if step_design_cost > 0 and best.source_item_id:
                agg = mat_totals.setdefault(
                    best.source_item_id,
                    {
                        "item_id": best.source_item_id,
                        "name": best.design_name,
                        "icon": best.design_icon,
                        "qty": 0,
                        "kind": "design",
                    },
                )
                agg["qty"] += 1
        step_mat += step_design_cost

        # 技能推进：未截断时整段走完；被确认次数截断时按期望涨点推进
        if capped:
            gained = _points_after_crafts(best, skill, crafts, params.prob_mode, probs, params.to_skill)
        else:
            gained = points

        steps.append(
            {
                "skill_from": skill,
                "skill_to": skill + gained,
                "recipe_id": best.id,
                "recipe_name": best.product_name,
                "product_item_id": best.product_item_id,
                "product_icon": best.product_icon,
                "crafts": crafts,
                "prob": prob,
                "prob_end": prob_end,
                "band": band,
                "disposition": best.disposition,
                "mat_cost": step_mat,
                "revenue": step_rev,
                "net": step_net,
                "confirmed": best.id in remaining,
                "source_type": best.source_type,
                "design_cost": step_design_cost,
                "design_name": step_design_name,
                # 成品 AH 无价 → 本步收入按卖店价估算（冷门信号，UI 提示用户可自行屏蔽）
                "revenue_fallback": best.revenue_fallback,
            }
        )
        # 拍卖行无价时已回退按 NPC 卖店价估算收入（见 _views 构造处）；物品数量大、
        # 缺价是常态，不再逐条警告（用户要求），静默处理。
        for m in best.mats:
            agg = mat_totals.setdefault(
                m.item_id,
                {"item_id": m.item_id, "name": m.name, "icon": m.icon, "qty": 0},
            )
            agg["qty"] += m.qty * crafts

        total_crafts += crafts
        total_mat += step_mat
        total_rev += step_rev
        skill = skill + gained

        # 确认次数消耗
        if best.id in remaining:
            remaining[best.id] -= crafts
            if remaining[best.id] < 0.5:
                remaining.pop(best.id, None)
                exhausted.add(best.id)
                excluded.append(
                    {
                        "recipe_id": best.id,
                        "name": best.product_name,
                        "reason": "确认次数已用完",
                    }
                )

    # 合并相邻的「同配方」步骤（即使跨档位边界也合并，同一产品连续做显示为一段；
    # 档位几率区间 prob→prob_end 自然展示 100%→20% 的衰减）
    merged_steps: list[dict] = []
    for st in steps:
        last = merged_steps[-1] if merged_steps else None
        if (
            last
            and last["recipe_id"] == st["recipe_id"]
            and abs(last["skill_to"] - st["skill_from"]) < 0.01
        ):
            last["skill_to"] = st["skill_to"]
            last["crafts"] += st["crafts"]
            last["mat_cost"] += st["mat_cost"]
            last["revenue"] += st["revenue"]
            last["net"] += st["net"]
            last["design_cost"] += st["design_cost"]
            last["prob_end"] = st["prob_end"]
            if st["design_name"] and not last["design_name"]:
                last["design_name"] = st["design_name"]
        else:
            merged_steps.append(dict(st))
    steps = merged_steps

    # 材料单价与来源
    materials = []
    for item_id, agg in mat_totals.items():
        ah = prices.get(item_id)
        # NPC 价：从配方行反推较麻烦，这里直接查一次
        npc = None
        limited = False
        if agg.get("kind") != "design":
            ms_kind = db.execute(
                select(MaterialSource.kind).where(
                    MaterialSource.profession_id == profession.id,
                    MaterialSource.item_id == item_id,
                )
            ).scalar_one_or_none()
            item = db.get(Item, item_id)
            limited = is_limited_vendor(item)
            if ms_kind == "vendor" and not limited:
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
                "icon": agg.get("icon"),
                "qty": agg["qty"],
                "unit_price": unit,
                "price_source": source,
                "cost": unit * agg["qty"] if unit is not None else None,
                "kind": agg.get("kind", "material"),
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
        # 同一配方可能在多个步骤出现，警告去重（保序），避免同一条文案刷屏
        "warnings": list(dict.fromkeys(warnings)),
        "excluded": excluded,
    }
