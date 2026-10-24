"""服务器（区服）路由。"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ..database import get_db
from ..models import PriceBatch, SavedRoute, Server
from ..schemas import ServerCreatedOut, ServerIn, ServerOut

router = APIRouter(prefix="/servers", tags=["servers"])


@router.get("", response_model=list[ServerOut])
def list_servers(db: Session = Depends(get_db)) -> list[ServerOut]:
    servers = db.execute(select(Server).order_by(Server.name)).scalars().all()
    batch_counts = dict(
        db.execute(select(PriceBatch.server_id, func.count()).group_by(PriceBatch.server_id)).all()
    )
    route_counts = dict(
        db.execute(select(SavedRoute.server_id, func.count()).group_by(SavedRoute.server_id)).all()
    )
    return [
        ServerOut(
            id=s.id,
            name=s.name,
            faction=s.faction,
            batch_count=batch_counts.get(s.id, 0),
            route_count=route_counts.get(s.id, 0),
            created_at=s.created_at,
        )
        for s in servers
    ]


@router.post("", response_model=ServerCreatedOut, status_code=201)
def create_server(payload: ServerIn, db: Session = Depends(get_db)) -> ServerCreatedOut:
    name = payload.name.strip()
    if not name:
        raise HTTPException(400, "服务器名称不能为空")
    existing = db.execute(select(Server).where(Server.name == name)).scalar_one_or_none()
    if existing:
        return ServerCreatedOut(id=existing.id, name=existing.name, faction=existing.faction, existed=True)
    server = Server(name=name, faction=payload.faction)
    db.add(server)
    db.commit()
    db.refresh(server)
    return ServerCreatedOut(id=server.id, name=server.name, faction=server.faction, existed=False)
