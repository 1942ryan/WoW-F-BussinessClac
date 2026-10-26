"""路线计算、保存与分享路由。"""

from __future__ import annotations

import json
import secrets

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..config import get_settings
from ..database import get_db
from ..models import Profession, SavedRoute, Server
from ..schemas import CalcIn, CalcOut, RouteDetailOut, RouteListItemOut, RouteSaveIn
from ..services.calc import calc_route

router = APIRouter(prefix="/routes", tags=["routes"])


def _calc_or_400(db: Session, params: CalcIn) -> dict:
    try:
        return calc_route(db, params, get_settings())
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc


@router.post("/calc", response_model=CalcOut)
def calculate(params: CalcIn, db: Session = Depends(get_db)) -> CalcOut:
    result = _calc_or_400(db, params)
    if db.get(Server, params.server_id) is None:
        raise HTTPException(404, "服务器不存在")
    server = db.get(Server, params.server_id)
    result["server"] = {"id": server.id, "name": server.name, "faction": server.faction}
    return CalcOut(**result)


@router.post("", response_model=RouteDetailOut, status_code=201)
def save_route(payload: RouteSaveIn, db: Session = Depends(get_db)) -> RouteDetailOut:
    server = db.get(Server, payload.server_id)
    if server is None:
        raise HTTPException(404, "服务器不存在")
    prof = db.execute(
        select(Profession).where(Profession.key == payload.profession_key)
    ).scalar_one_or_none()
    if prof is None:
        raise HTTPException(404, f"专业不存在: {payload.profession_key}")
    if payload.to_skill <= payload.from_skill:
        raise HTTPException(400, "目标技能必须大于当前技能")

    params = CalcIn(
        server_id=payload.server_id,
        profession_key=payload.profession_key,
        from_skill=payload.from_skill,
        to_skill=payload.to_skill,
        price_mode=payload.price_mode,
        product_disposition=payload.product_disposition,
        blocked_recipe_ids=payload.blocked_recipe_ids,
        blocked_item_ids=payload.blocked_item_ids,
        confirmed_recipe_ids=payload.confirmed_recipe_ids,
        confirmed_counts=payload.confirmed_counts,
        recipe_dispositions=payload.recipe_dispositions,
        include_designs=payload.include_designs,
        design_cost=payload.design_cost,
        prob_mode=payload.prob_mode,
        prob_orange=payload.prob_orange,
        prob_yellow=payload.prob_yellow,
        prob_green=payload.prob_green,
    )
    result = _calc_or_400(db, params)

    route = SavedRoute(
        server_id=payload.server_id,
        profession_id=prof.id,
        from_skill=payload.from_skill,
        to_skill=payload.to_skill,
        title=payload.title.strip(),
        author=(payload.author or "").strip() or None,
        notes=(payload.notes or "").strip() or None,
        price_mode=payload.price_mode,
        product_disposition=payload.product_disposition,
        blocked_recipe_ids=json.dumps(payload.blocked_recipe_ids, ensure_ascii=False),
        blocked_item_ids=json.dumps(payload.blocked_item_ids, ensure_ascii=False),
        confirmed_recipe_ids=json.dumps(payload.confirmed_recipe_ids, ensure_ascii=False),
        confirmed_counts=json.dumps(payload.confirmed_counts, ensure_ascii=False),
        recipe_dispositions=json.dumps(payload.recipe_dispositions, ensure_ascii=False),
        include_designs=payload.include_designs,
        design_cost=payload.design_cost,
        prob_mode=payload.prob_mode,
        prob_orange=payload.prob_orange,
        prob_yellow=payload.prob_yellow,
        prob_green=payload.prob_green,
        steps=json.dumps(result["steps"], ensure_ascii=False),
        totals=json.dumps(result["totals"], ensure_ascii=False),
        materials=json.dumps(result.get("materials", []), ensure_ascii=False),
        is_public=payload.is_public,
        share_code=secrets.token_urlsafe(8)[:10],
    )
    db.add(route)
    db.commit()
    db.refresh(route)
    return _detail_out(db, route, result)


def _detail_out(db: Session, route: SavedRoute, result: dict | None = None) -> RouteDetailOut:
    if result is None:
        result = {
            "steps": json.loads(route.steps),
            "totals": json.loads(route.totals),
            "materials": json.loads(route.materials) if route.materials else [],
            "warnings": [],
        }
    server = db.get(Server, route.server_id)
    prof = db.get(Profession, route.profession_id)
    params = {
        "server_id": route.server_id,
        "profession_key": prof.key if prof else "",
        "from_skill": route.from_skill,
        "to_skill": route.to_skill,
        "price_mode": route.price_mode,
        "product_disposition": route.product_disposition,
        "blocked_recipe_ids": json.loads(route.blocked_recipe_ids),
        "blocked_item_ids": json.loads(route.blocked_item_ids),
        "confirmed_recipe_ids": json.loads(route.confirmed_recipe_ids),
        "confirmed_counts": json.loads(route.confirmed_counts or "{}"),
        "recipe_dispositions": json.loads(route.recipe_dispositions or "{}"),
        "include_designs": route.include_designs,
        "design_cost": route.design_cost,
        "prob_mode": route.prob_mode or "formula",
        "prob_orange": route.prob_orange,
        "prob_yellow": route.prob_yellow,
        "prob_green": route.prob_green,
    }
    return RouteDetailOut(
        id=route.id,
        share_code=route.share_code,
        title=route.title,
        author=route.author,
        notes=route.notes,
        server=(
            {"id": server.id, "name": server.name, "faction": server.faction} if server else {}
        ),
        profession={"key": prof.key, "name": prof.name} if prof else {},
        params=params,
        steps=result["steps"],
        totals=result["totals"],
        materials=result.get("materials", []),
        warnings=result.get("warnings", []),
        is_public=route.is_public,
        created_at=route.created_at,
    )


@router.get("", response_model=list[RouteListItemOut])
def list_routes(
    server_id: int | None = None,
    profession_key: str | None = None,
    public_only: bool = True,
    db: Session = Depends(get_db),
) -> list[RouteListItemOut]:
    stmt = select(SavedRoute).order_by(SavedRoute.id.desc()).limit(100)
    if public_only:
        stmt = stmt.where(SavedRoute.is_public.is_(True))
    if server_id:
        stmt = stmt.where(SavedRoute.server_id == server_id)
    if profession_key:
        prof = db.execute(
            select(Profession).where(Profession.key == profession_key)
        ).scalar_one_or_none()
        if prof:
            stmt = stmt.where(SavedRoute.profession_id == prof.id)
    routes = db.execute(stmt).scalars().all()
    out: list[RouteListItemOut] = []
    for r in routes:
        server = db.get(Server, r.server_id)
        prof = db.get(Profession, r.profession_id)
        totals = json.loads(r.totals)
        out.append(
            RouteListItemOut(
                id=r.id,
                share_code=r.share_code,
                title=r.title,
                author=r.author,
                server_name=server.name if server else "-",
                server_faction=(server.faction if server else None) or "both",
                profession_name=prof.name if prof else "-",
                profession_key=prof.key if prof else "",
                from_skill=r.from_skill,
                to_skill=r.to_skill,
                price_mode=r.price_mode,
                net=totals.get("net", 0),
                net_display=totals.get("net_display", "-"),
                is_public=r.is_public,
                created_at=r.created_at,
            )
        )
    return out


@router.get("/{share_code}", response_model=RouteDetailOut)
def route_detail(share_code: str, db: Session = Depends(get_db)) -> RouteDetailOut:
    route = db.execute(
        select(SavedRoute).where(SavedRoute.share_code == share_code)
    ).scalar_one_or_none()
    if route is None:
        raise HTTPException(404, "路线不存在")
    detail = _detail_out(db, route)
    if not detail.materials:
        # 老路线没有材料清单快照 → 按当前价格补算一次（只用于展示采购清单，
        # steps/totals 仍用保存时的快照，避免数字前后不一致）
        try:
            prof = db.get(Profession, route.profession_id)
            params = CalcIn(
                server_id=route.server_id,
                profession_key=prof.key if prof else "",
                from_skill=route.from_skill,
                to_skill=route.to_skill,
                price_mode=route.price_mode,
                product_disposition=route.product_disposition,
                blocked_recipe_ids=json.loads(route.blocked_recipe_ids),
                blocked_item_ids=json.loads(route.blocked_item_ids),
                confirmed_recipe_ids=json.loads(route.confirmed_recipe_ids),
                confirmed_counts=json.loads(route.confirmed_counts or "{}"),
                recipe_dispositions=json.loads(route.recipe_dispositions or "{}"),
                include_designs=route.include_designs,
                design_cost=route.design_cost,
                prob_mode=route.prob_mode or "formula",
                prob_orange=route.prob_orange,
                prob_yellow=route.prob_yellow,
                prob_green=route.prob_green,
            )
            detail.materials = calc_route(db, params, get_settings()).get("materials", [])
        except (ValueError, KeyError):
            pass
    return detail


@router.post("/{share_code}/recalc", response_model=CalcOut)
def route_recalc(share_code: str, db: Session = Depends(get_db)) -> CalcOut:
    """采用他人路线：用其参数按当前价格重算。"""
    route = db.execute(
        select(SavedRoute).where(SavedRoute.share_code == share_code)
    ).scalar_one_or_none()
    if route is None:
        raise HTTPException(404, "路线不存在")
    prof = db.get(Profession, route.profession_id)
    params = CalcIn(
        server_id=route.server_id,
        profession_key=prof.key if prof else "",
        from_skill=route.from_skill,
        to_skill=route.to_skill,
        price_mode=route.price_mode,
        product_disposition=route.product_disposition,
        blocked_recipe_ids=json.loads(route.blocked_recipe_ids),
        blocked_item_ids=json.loads(route.blocked_item_ids),
        confirmed_recipe_ids=json.loads(route.confirmed_recipe_ids),
        confirmed_counts={int(k): v for k, v in json.loads(route.confirmed_counts or "{}").items()},
        recipe_dispositions={
            int(k): v for k, v in json.loads(route.recipe_dispositions or "{}").items()
        },
        include_designs=route.include_designs,
        design_cost=route.design_cost,
        prob_mode=route.prob_mode or "formula",
        prob_orange=route.prob_orange,
        prob_yellow=route.prob_yellow,
        prob_green=route.prob_green,
    )
    result = _calc_or_400(db, params)
    server = db.get(Server, route.server_id)
    result["server"] = (
        {"id": server.id, "name": server.name, "faction": server.faction} if server else {}
    )
    return CalcOut(**result)
