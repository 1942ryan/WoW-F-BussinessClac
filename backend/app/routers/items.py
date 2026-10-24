"""物品搜索路由（价格导入校对 / 手动录价用）。"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from ..database import get_db
from ..models import Item
from ..services.importer import normalize_name

router = APIRouter(prefix="/items", tags=["items"])


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


@router.get("/{item_id}")
def item_detail(item_id: int, db: Session = Depends(get_db)) -> dict:
    item = db.get(Item, item_id)
    if item is None:
        raise HTTPException(404, "物品不存在")
    return {
        "item_id": item.id,
        "name": item.name,
        "name_en": item.name_en,
        "quality": item.quality,
        "item_level": item.item_level,
        "type": item.type,
        "status": item.status,
        "icon": item.icon,
        "vendor_price": item.vendor_price,
    }
