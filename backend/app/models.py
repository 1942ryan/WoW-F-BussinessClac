"""ORM 模型（SQLAlchemy 2.0 声明式）。"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import (
    Boolean,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .database import Base


class Server(Base):
    __tablename__ = "servers"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    batches: Mapped[list["PriceBatch"]] = relationship(back_populates="server")
    routes: Mapped[list["SavedRoute"]] = relationship(back_populates="server")


class Item(Base):
    """物品主数据（种子数据，来自无限官方数据库）。"""

    __tablename__ = "items"

    id: Mapped[int] = mapped_column(primary_key=True)  # WoW 物品 ID
    name: Mapped[str] = mapped_column(String(128), index=True)
    name_en: Mapped[str | None] = mapped_column(String(128))
    quality: Mapped[int] = mapped_column(Integer, default=0)
    item_level: Mapped[int | None] = mapped_column(Integer)
    type: Mapped[str | None] = mapped_column(String(64))  # 英文子类型，如 Metal & Stone
    class_id: Mapped[int | None] = mapped_column(Integer)
    status: Mapped[str | None] = mapped_column(String(16))  # new/rebuilt/changed/same/missing
    icon: Mapped[str | None] = mapped_column(String(256))  # 图标 URL（无限官方库）
    vendor_price: Mapped[int] = mapped_column(Integer, default=0)  # 卖店价（铜）


class Profession(Base):
    __tablename__ = "professions"

    id: Mapped[int] = mapped_column(primary_key=True)
    key: Mapped[str] = mapped_column(String(32), unique=True)
    name: Mapped[str] = mapped_column(String(32))

    recipes: Mapped[list["Recipe"]] = relationship(back_populates="profession")


class Recipe(Base):
    __tablename__ = "recipes"
    # 同一专业下同一成品物品只保留一条；附魔类成品无物品 ID，按名称区分
    __table_args__ = (
        UniqueConstraint(
            "profession_id", "product_item_id", "product_name", name="uq_recipe_product"
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    profession_id: Mapped[int] = mapped_column(ForeignKey("professions.id"), index=True)
    product_item_id: Mapped[int | None] = mapped_column(ForeignKey("items.id"), index=True)
    product_name: Mapped[str] = mapped_column(String(160))
    product_kind: Mapped[str] = mapped_column(String(16), default="item")  # item | enchant
    product_qty: Mapped[int] = mapped_column(Integer, default=1)  # 单次产出数量
    is_new: Mapped[bool] = mapped_column(Boolean, default=False)  # 无限新增
    skill_orange: Mapped[int] = mapped_column(Integer)  # 学会（橙档起点）
    skill_yellow: Mapped[int] = mapped_column(Integer)
    skill_green: Mapped[int] = mapped_column(Integer)
    skill_gray: Mapped[int] = mapped_column(Integer)
    source_type: Mapped[str] = mapped_column(String(32))  # 训练师/设计图/商人/掉落...
    source_item_id: Mapped[int | None] = mapped_column(ForeignKey("items.id"))

    profession: Mapped[Profession] = relationship(back_populates="recipes")
    product_item: Mapped[Item | None] = relationship(foreign_keys=[product_item_id])
    source_item: Mapped[Item | None] = relationship(foreign_keys=[source_item_id])
    materials: Mapped[list["RecipeMaterial"]] = relationship(
        back_populates="recipe", cascade="all, delete-orphan"
    )


class RecipeMaterial(Base):
    __tablename__ = "recipe_materials"
    __table_args__ = (UniqueConstraint("recipe_id", "item_id", name="uq_recipe_material"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    recipe_id: Mapped[int] = mapped_column(ForeignKey("recipes.id"), index=True)
    item_id: Mapped[int] = mapped_column(ForeignKey("items.id"), index=True)
    qty: Mapped[int] = mapped_column(Integer)

    recipe: Mapped[Recipe] = relationship(back_populates="materials")
    item: Mapped[Item] = relationship()


class MaterialSource(Base):
    """购物清单标注的材料来源（按专业）：vendor=商人出售 / gather_ah=采集或拍卖行 / crafted=途中自制。"""

    __tablename__ = "material_sources"
    __table_args__ = (UniqueConstraint("profession_id", "item_id", name="uq_material_source"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    profession_id: Mapped[int] = mapped_column(ForeignKey("professions.id"), index=True)
    item_id: Mapped[int] = mapped_column(ForeignKey("items.id"), index=True)
    kind: Mapped[str] = mapped_column(String(16))


class PriceBatch(Base):
    """一次价格导入（AUC 导出 / 手动）。"""

    __tablename__ = "price_batches"

    id: Mapped[int] = mapped_column(primary_key=True)
    server_id: Mapped[int] = mapped_column(ForeignKey("servers.id"), index=True)
    filename: Mapped[str | None] = mapped_column(String(160))
    source: Mapped[str] = mapped_column(String(16), default="auc")  # auc | manual
    row_count: Mapped[int] = mapped_column(Integer, default=0)
    matched: Mapped[int] = mapped_column(Integer, default=0)
    unmatched: Mapped[int] = mapped_column(Integer, default=0)
    imported_by: Mapped[str | None] = mapped_column(String(64))
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    server: Mapped[Server] = relationship(back_populates="batches")
    records: Mapped[list["PriceRecord"]] = relationship(
        back_populates="batch", cascade="all, delete-orphan"
    )


class PriceRecord(Base):
    """单条价格流水：某服务器某物品在某次导入时的单价（铜）。"""

    __tablename__ = "price_records"

    id: Mapped[int] = mapped_column(primary_key=True)
    batch_id: Mapped[int] = mapped_column(ForeignKey("price_batches.id"), index=True)
    server_id: Mapped[int] = mapped_column(ForeignKey("servers.id"), index=True)
    item_id: Mapped[int] = mapped_column(ForeignKey("items.id"), index=True)
    unit_price: Mapped[int] = mapped_column(Integer)  # 铜
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    batch: Mapped[PriceBatch] = relationship(back_populates="records")
    item: Mapped[Item] = relationship()


class SavedRoute(Base):
    """保存/分享的冲级路线。steps/totals 为计算快照，params 用于他人采用后重算。"""

    __tablename__ = "saved_routes"

    id: Mapped[int] = mapped_column(primary_key=True)
    server_id: Mapped[int] = mapped_column(ForeignKey("servers.id"), index=True)
    profession_id: Mapped[int] = mapped_column(ForeignKey("professions.id"), index=True)
    from_skill: Mapped[int] = mapped_column(Integer)
    to_skill: Mapped[int] = mapped_column(Integer)
    title: Mapped[str] = mapped_column(String(160))
    author: Mapped[str | None] = mapped_column(String(64))
    notes: Mapped[str | None] = mapped_column(Text)
    price_mode: Mapped[str] = mapped_column(String(16), default="latest")
    product_disposition: Mapped[str] = mapped_column(String(16), default="sell_ah")
    blocked_recipe_ids: Mapped[str] = mapped_column(Text, default="[]")  # JSON
    blocked_item_ids: Mapped[str] = mapped_column(Text, default="[]")  # JSON
    confirmed_recipe_ids: Mapped[str] = mapped_column(Text, default="[]")  # JSON
    include_designs: Mapped[bool] = mapped_column(Boolean, default=True)
    design_cost: Mapped[str] = mapped_column(String(8), default="ah", server_default="ah")  # ah | drop
    steps: Mapped[str] = mapped_column(Text, default="[]")  # JSON 快照
    totals: Mapped[str] = mapped_column(Text, default="{}")  # JSON 快照
    is_public: Mapped[bool] = mapped_column(Boolean, default=True, index=True)
    share_code: Mapped[str] = mapped_column(String(16), unique=True, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    server: Mapped[Server] = relationship(back_populates="routes")
    profession: Mapped[Profession] = relationship()
