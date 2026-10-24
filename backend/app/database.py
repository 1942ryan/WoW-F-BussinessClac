"""数据库引擎与会话管理（SQLAlchemy 2.0）。"""

from __future__ import annotations

from collections.abc import Iterator

from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from .config import get_settings

_settings = get_settings()

_connect_args = {}
if _settings.database_url.startswith("sqlite"):
    _connect_args = {"check_same_thread": False}

engine = create_engine(
    _settings.database_url,
    echo=False,
    future=True,
    connect_args=_connect_args,
    pool_pre_ping=True,
)

SessionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)


class Base(DeclarativeBase):
    pass


def get_db() -> Iterator[Session]:
    """请求级会话依赖：yield 模式，用完即关。"""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db() -> None:
    """建表（开发/种子用；生产建议 Alembic，见 README）。"""
    from . import models  # noqa: F401  确保模型已注册

    Base.metadata.create_all(engine)
