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
from ..services.calc import effective_prices
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
    if server_id:
        prices = effective_prices(db, server_id, "latest", get_settings().median_window_days)
        effective_ah = prices.get(item_id)
        record_count = (
            db.execute(
                select(func.count()).select_from(PriceRecord).where(
                    PriceRecord.server_id == server_id, PriceRecord.item_id == item_id
                )
            ).scalar()
            or 0
        )
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
        tooltip=_tooltip_lines(item.tooltip),
    )
