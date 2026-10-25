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
    """建表（开发/种子用；生产建议 Alembic，见 README）。

    create_all 只建新表、不改旧表，所以这里顺手补一遍 SQLite 上后加的列，
    免得老库升级后出现 "no such column"。
    """
    from . import models  # noqa: F401  确保模型已注册

    Base.metadata.create_all(engine)
    _ensure_columns()


# (表名, 列名, DDL 类型)；缺哪列补哪列，已存在则跳过
_EXTRA_COLUMNS: list[tuple[str, str, str]] = [
    ("recipes", "source_note", "VARCHAR(200)"),
    # 贸易营地（艾泽拉斯贸易局 / 杜隆塔尔补给后勤部）出售的图纸需要「商人青睐」点数
    ("recipes", "vendor_favor", "INTEGER"),
]


def _ensure_columns() -> None:
    if not _settings.database_url.startswith("sqlite"):
        return
    with engine.connect() as conn:
        for table, column, ddl in _EXTRA_COLUMNS:
            cols = [row[1] for row in conn.exec_driver_sql(f"PRAGMA table_info({table})")]
            if cols and column not in cols:
                conn.exec_driver_sql(f"ALTER TABLE {table} ADD COLUMN {column} {ddl}")
                conn.commit()
