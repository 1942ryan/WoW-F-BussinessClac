"""物品搜索路由（价格导入校对 / 手动录价 / 图标悬停详情用）。"""

from __future__ import annotations

import json

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from ..config import get_settings
from ..database import get_db
from ..models import Item, PriceRecord
from ..schemas import ItemDetailOut
from ..services.calc import latest_price_records, price_age_hours
from ..services.importer import normalize_name

router = APIRouter(prefix="/items", tags=["items"])


def _tooltip_lines(raw: str | None) -> list[str]:
    """items.tooltip 存的是 JSON 字符串数组；脏数据一律当空，不抛 500。"""
    if not raw:
        return []
    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        return []
    if not isinstance(data, list):
        return []
    return [str(x) for x in data if isinstance(x, str)]


@router.get("/search")
def search_items(
    q: str = Query(min_length=1, max_length=64),
    limit: int = Query(default=20, le=50),
    db: Session = Depends(get_db),
) -> list[dict]:
    qn = normalize_name(q)
    items = db.execute(select(Item).limit(5000)).scalars().all()
    matched = [i for i in items if qn in normalize_name(i.name)]
    matched.sort(key=lambda i: (not normalize_name(i.name).startswith(qn), len(i.name)))
    return [
        {
            "item_id": i.id,
            "name": i.name,
            "name_en": i.name_en,
            "quality": i.quality,
            "icon": i.icon,
            "vendor_price": i.vendor_price,
        }
        for i in matched[:limit]
    ]


@router.get("/{item_id}", response_model=ItemDetailOut)
def item_detail(item_id: int, server_id: int | None = Query(default=None), db: Session = Depends(get_db)) -> ItemDetailOut:
    """物品详情（悬停 tooltip 用）：等级/类型/卖店价 + 当前服务器拍卖行有效价。"""
    item = db.get(Item, item_id)
    if item is None:
        raise HTTPException(404, "物品不存在")
    effective_ah: int | None = None
    record_count = 0
    price_updated_at = None
    age_hours: float | None = None
    if server_id:
        records = latest_price_records(db, server_id)
        price_updated_at = records[item_id][1] if item_id in records else None
        effective_ah = records[item_id][0] if item_id in records else None
        age_hours = price_age_hours(price_updated_at)
        record_count = (
            db.execute(
                select(func.count()).select_from(PriceRecord).where(
                    PriceRecord.server_id == server_id, PriceRecord.item_id == item_id
                )
            ).scalar()
            or 0
        )
    valid_hours = get_settings().price_valid_hours
    return ItemDetailOut(
        item_id=item.id,
        name=item.name,
        name_en=item.name_en,
        quality=item.quality or 0,
        item_level=item.item_level,
        type=item.type,
        status=item.status,
        icon=item.icon,
        vendor_price=item.vendor_price,
        effective_ah=effective_ah,
        record_count=record_count,
        price_updated_at=price_updated_at,
        price_age_hours=age_hours,
        price_stale=bool(age_hours is not None and age_hours > valid_hours),
        price_valid_hours=valid_hours,
        tooltip=_tooltip_lines(item.tooltip),
    )
