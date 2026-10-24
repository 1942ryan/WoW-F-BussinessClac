"""pytest 共享 fixture：独立临时 SQLite 库 + 测试客户端。"""

from __future__ import annotations

import os
from pathlib import Path

import pytest

# 必须在导入 app 之前设置（config 在导入时读取）
_TMP_DB = Path(__file__).resolve().parent / "test_wowfc.db"
os.environ["WOWFC_DATABASE_URL"] = f"sqlite:///{_TMP_DB.as_posix()}"

from fastapi.testclient import TestClient  # noqa: E402

from app.database import Base, SessionLocal, engine  # noqa: E402
from app.main import app  # noqa: E402
from app.models import Item, MaterialSource, Profession, Recipe, RecipeMaterial, Server  # noqa: E402


@pytest.fixture(autouse=True)
def clean_db():
    Base.metadata.drop_all(engine)
    Base.metadata.create_all(engine)
    yield
    Base.metadata.drop_all(engine)


@pytest.fixture
def db_session():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


@pytest.fixture
def client():
    return TestClient(app)


# ---------- 测试数据工厂 ----------


def make_item(db, item_id: int, name: str, vendor_price: int = 0, quality: int = 1, item_level: int | None = None, icon: str | None = None) -> Item:
    item = Item(
        id=item_id,
        name=name,
        quality=quality,
        vendor_price=vendor_price,
        item_level=item_level,
        icon=icon,
    )
    db.add(item)
    db.flush()
    return item


def make_profession(db, key: str = "test", name: str = "测试专业") -> Profession:
    prof = Profession(key=key, name=name)
    db.add(prof)
    db.flush()
    return prof


def make_recipe(
    db,
    prof: Profession,
    product_item: Item | None,
    product_name: str,
    mats: list[tuple[Item, int]],
    orange: int,
    yellow: int,
    green: int,
    gray: int,
    source_type: str = "trainer",
    product_qty: int = 1,
    source_item: Item | None = None,
) -> Recipe:
    r = Recipe(
        profession_id=prof.id,
        product_item_id=product_item.id if product_item else None,
        product_name=product_name,
        product_kind="item" if product_item else "enchant",
        product_qty=product_qty,
        skill_orange=orange,
        skill_yellow=yellow,
        skill_green=green,
        skill_gray=gray,
        source_type=source_type,
        source_item_id=source_item.id if source_item else None,
    )
    db.add(r)
    db.flush()
    for item, qty in mats:
        db.add(RecipeMaterial(recipe_id=r.id, item_id=item.id, qty=qty))
    db.flush()
    return r


def make_server(db, name: str = "测试服") -> Server:
    s = Server(name=name)
    db.add(s)
    db.flush()
    return s


def add_price(db, server: Server, item: Item, price: int, batch_seq: int = 1) -> None:
    from app.models import PriceBatch, PriceRecord

    batch = PriceBatch(server_id=server.id, filename=f"t{batch_seq}.csv", row_count=1, matched=1)
    db.add(batch)
    db.flush()
    db.add(PriceRecord(batch_id=batch.id, server_id=server.id, item_id=item.id, unit_price=price))
    db.flush()
