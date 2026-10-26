"""价格导入与查询路由。"""

from __future__ import annotations

import json

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, UploadFile
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ..config import get_settings
from ..database import get_db
from ..models import FACTION_BOTH, Item, PriceBatch, PriceRecord, Server
from ..services.calc import effective_prices, latest_price_records, price_age_hours
from ..schemas import (
    EffectivePriceOut,
    ImportSummaryOut,
    ItemPriceOut,
    ManualPriceIn,
    PriceFreshnessOut,
    PriceHistoryPointOut,
)
from ..services.importer import ImportParseError, normalize_name, parse_csv

router = APIRouter(prefix="/prices", tags=["prices"])


def _resolve_items(db: Session) -> tuple[dict[str, list[tuple[int, int | None]]], dict[str, list[tuple[int, int | None]]]]:
    """返回 (精确名称→[(id, 物品等级)], 归一化名称→[(id, 物品等级)])。

    无限版存在同名不同物品（如「劣质炸药」4358/4365，物品等级 10/20），
    导入时若 AUC 导出带物品等级列，可据此精确消歧。
    """
    exact: dict[str, list[tuple[int, int | None]]] = {}
    normalized: dict[str, list[tuple[int, int | None]]] = {}
    for item in db.execute(select(Item.id, Item.name, Item.item_level)).all():
        exact.setdefault(item.name, []).append((item.id, item.item_level))
        normalized.setdefault(normalize_name(item.name), []).append((item.id, item.item_level))
    return exact, normalized


def _match_item(
    row,
    exact: dict[str, list[tuple[int, int | None]]],
    normalized: dict[str, list[tuple[int, int | None]]],
) -> list[int]:
    """一行导入数据 → 匹配到的物品 ID 列表（可能多个：同名且无等级可消歧）。"""
    if row.item_id is not None:
        return [row.item_id]
    candidates = exact.get(row.raw_name) or normalized.get(normalize_name(row.raw_name)) or []
    if not candidates:
        return []
    if len(candidates) == 1:
        return [candidates[0][0]]
    # 同名多个物品：优先按物品等级精确匹配
    if row.item_level is not None:
        by_level = [i for i, lvl in candidates if lvl == row.item_level]
        if by_level:
            return by_level
    # 无等级信息：同名物品全部赋同一价格（用户可事后手动微调）
    return [i for i, _ in candidates]


@router.post("/import", response_model=ImportSummaryOut)
async def import_prices(
    file: UploadFile = File(...),
    server_id: int = Form(...),
    imported_by: str | None = Form(default=None),
    db: Session = Depends(get_db),
) -> ImportSummaryOut:
    server = db.get(Server, server_id)
    if server is None:
        raise HTTPException(404, "服务器不存在")
    data = await file.read()
    if len(data) > 5 * 1024 * 1024:
        raise HTTPException(413, "文件过大（上限 5MB）")
    try:
        rows = parse_csv(data)
    except ImportParseError as exc:
        raise HTTPException(400, str(exc)) from exc

    exact, normalized = _resolve_items(db)
    existing_ids = {
        i for (i,) in db.execute(select(Item.id)).all()
    }
    faction = server.faction or FACTION_BOTH
    records: list[PriceRecord] = []
    unmatched: list[str] = []
    matched_rows = 0
    for row in rows:
        ids = [i for i in _match_item(row, exact, normalized) if i in existing_ids]
        if not ids:
            unmatched.append(row.raw_name)
            continue
        matched_rows += 1
        records.extend(
            PriceRecord(server_id=server_id, item_id=item_id, unit_price=row.price, faction=faction)
            for item_id in ids
        )

    batch = PriceBatch(
        server_id=server_id,
        filename=file.filename,
        source="auc",
        row_count=len(rows),
        matched=matched_rows,
        unmatched=len(unmatched),
        imported_by=(imported_by or "").strip() or None,
    )
    db.add(batch)
    db.flush()
    for rec in records:
        rec.batch_id = batch.id
    db.add_all(records)
    db.commit()
    return ImportSummaryOut(
        batch_id=batch.id,
        row_count=len(rows),
        matched=matched_rows,
        unmatched=len(unmatched),
        inserted=len(records),
        unmatched_names=sorted(set(unmatched))[:50],
    )


@router.post("/manual", response_model=ImportSummaryOut)
def manual_price(payload: ManualPriceIn, db: Session = Depends(get_db)) -> ImportSummaryOut:
    if db.get(Server, payload.server_id) is None:
        raise HTTPException(404, "服务器不存在")
    if db.get(Item, payload.item_id) is None:
        raise HTTPException(404, "物品不存在")
    batch = PriceBatch(
        server_id=payload.server_id,
        filename=None,
        source="manual",
        row_count=1,
        matched=1,
        unmatched=0,
        imported_by=(payload.imported_by or "").strip() or None,
    )
    db.add(batch)
    db.flush()
    server = db.get(Server, payload.server_id)
    faction = (server.faction if server else None) or FACTION_BOTH
    db.add(
        PriceRecord(
            batch_id=batch.id,
            server_id=payload.server_id,
            item_id=payload.item_id,
            unit_price=payload.unit_price,
            faction=faction,
        )
    )
    db.commit()
    return ImportSummaryOut(
        batch_id=batch.id,
        row_count=1,
        matched=1,
        unmatched=0,
        inserted=1,
    )


@router.get("/batches")
def list_batches(server_id: int, db: Session = Depends(get_db)) -> list[dict]:
    rows = db.execute(
        select(PriceBatch)
        .where(PriceBatch.server_id == server_id)
        .order_by(PriceBatch.id.desc())
        .limit(50)
    ).scalars().all()
    return [
        {
            "id": b.id,
            "filename": b.filename,
            "source": b.source,
            "row_count": b.row_count,
            "matched": b.matched,
            "unmatched": b.unmatched,
            "imported_by": b.imported_by,
            "created_at": b.created_at,
        }
        for b in rows
    ]


def _faction_scope(db: Session, server_id: int):
    """返回该服务器可见的阵营条件（None=不区分）。"""
    server = db.get(Server, server_id)
    faction = (server.faction if server else None) or FACTION_BOTH
    if faction == FACTION_BOTH:
        return None
    return (PriceRecord.faction == faction) | (PriceRecord.faction == FACTION_BOTH)


@router.get("/freshness", response_model=PriceFreshnessOut)
def price_freshness(server_id: int, db: Session = Depends(get_db)) -> PriceFreshnessOut:
    """云价格有效期：本服最近一次导入是什么时候、有多少物品/多少条已过期。

    前端在计划页顶部用它显示「价格数据 N 小时前更新（有效期 24h）」，
    超期就提示重新导价，不改变计算口径。
    """
    settings = get_settings()
    valid_hours = settings.price_valid_hours
    server = db.get(Server, server_id)
    if server is None:
        raise HTTPException(404, "服务器不存在")

    last_batch = db.execute(
        select(PriceBatch)
        .where(PriceBatch.server_id == server_id)
        .order_by(PriceBatch.id.desc())
        .limit(1)
    ).scalar_one_or_none()
    batch_count = (
        db.execute(
            select(func.count()).select_from(PriceBatch).where(PriceBatch.server_id == server_id)
        ).scalar()
        or 0
    )

    records = latest_price_records(db, server_id)
    ages = [a for a in (price_age_hours(at) for _, at in records.values()) if a is not None]
    last_at = last_batch.created_at if last_batch else (max((at for _, at in records.values() if at), default=None))
    age = price_age_hours(last_at)
    return PriceFreshnessOut(
        server_id=server_id,
        server_name=server.name,
        last_import_at=last_at,
        age_hours=age,
        batch_count=batch_count,
        item_count=len(records),
        stale_items=sum(1 for a in ages if a > valid_hours),
        oldest_age_hours=max(ages) if ages else None,
        last_imported_by=last_batch.imported_by if last_batch else None,
        valid_hours=valid_hours,
        stale=bool(age is not None and age > valid_hours),
    )


@router.get("", response_model=list[EffectivePriceOut])
def effective_prices_list(
    server_id: int,
    mode: str = Query(default="latest", pattern="^(latest|median)$"),
    q: str | None = Query(default=None),
    limit: int = Query(default=200, le=1000),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
) -> list[EffectivePriceOut]:
    prices = effective_prices(db, server_id, mode, get_settings().median_window_days)
    faction_cond = _faction_scope(db, server_id)

    def _rec(stmt):
        stmt = stmt.where(PriceRecord.server_id == server_id)
        if faction_cond is not None:
            stmt = stmt.where(faction_cond)
        return stmt

    counts = dict(
        db.execute(
            _rec(select(PriceRecord.item_id, func.count()).group_by(PriceRecord.item_id))
        ).all()
    )
    last_at = dict(
        db.execute(
            _rec(
                select(PriceRecord.item_id, func.max(PriceRecord.created_at)).group_by(
                    PriceRecord.item_id
                )
            )
        ).all()
    )
    item_ids = sorted(prices)
    if q:
        qn = normalize_name(q)
        name_map = {i.id: i.name for i in db.execute(select(Item).where(Item.id.in_(item_ids))).scalars().all()}
        item_ids = [i for i in item_ids if qn in normalize_name(name_map.get(i, ""))]
    page = item_ids[offset : offset + limit]
    items = {i.id: i for i in db.execute(select(Item).where(Item.id.in_(page))).scalars().all()}
    return [
        EffectivePriceOut(
            item_id=i,
            name=items[i].name if i in items else f"物品{i}",
            icon=items[i].icon if i in items else None,
            price=prices[i],
            mode=mode,
            record_count=counts.get(i, 0),
            last_at=last_at.get(i),
        )
        for i in page
    ]


@router.get("/item/{item_id}", response_model=ItemPriceOut)
def item_price_detail(
    item_id: int, server_id: int, db: Session = Depends(get_db)
) -> ItemPriceOut:
    item = db.get(Item, item_id)
    if item is None:
        raise HTTPException(404, "物品不存在")
    prices = effective_prices(db, server_id, "latest", get_settings().median_window_days)
    faction_cond = _faction_scope(db, server_id)
    hist_stmt = (
        select(PriceRecord, PriceBatch.imported_by, PriceBatch.source)
        .join(PriceBatch, PriceRecord.batch_id == PriceBatch.id)
        .where(PriceRecord.server_id == server_id, PriceRecord.item_id == item_id)
        .order_by(PriceRecord.id.desc())
        .limit(100)
    )
    if faction_cond is not None:
        hist_stmt = hist_stmt.where(faction_cond)
    history = db.execute(hist_stmt).all()
    return ItemPriceOut(
        item_id=item.id,
        name=item.name,
        icon=item.icon,
        name_en=item.name_en,
        quality=item.quality,
        vendor_price=item.vendor_price,
        effective_ah=prices.get(item_id),
        effective_mode="latest",
        record_count=len(history),
        history=[
            PriceHistoryPointOut(
                batch_id=rec.batch_id,
                unit_price=rec.unit_price,
                created_at=rec.created_at,
                imported_by=imported_by,
            )
            for rec, imported_by, _src in history
        ],
    )
