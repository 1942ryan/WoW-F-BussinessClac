"""Pydantic 请求/响应模型。"""

from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field

PriceMode = Literal["latest", "median"]
Disposition = Literal["sell_ah", "sell_npc", "self_use"]
DesignCost = Literal["ah", "drop"]


# ---------- 通用 ----------


class OkOut(BaseModel):
    ok: bool = True
    message: str = ""


# ---------- 服务器 ----------


class ServerIn(BaseModel):
    name: str = Field(min_length=1, max_length=64)


class ServerOut(BaseModel):
    id: int
    name: str
    batch_count: int = 0
    route_count: int = 0
    created_at: datetime | None = None

    model_config = {"from_attributes": True}


class ServerCreatedOut(BaseModel):
    id: int
    name: str
    existed: bool


# ---------- 专业与配方 ----------


class ProfessionOut(BaseModel):
    id: int
    key: str
    name: str
    recipe_count: int = 0
    max_skill: int = 0

    model_config = {"from_attributes": True}


class MaterialOut(BaseModel):
    item_id: int
    name: str
    icon: str | None = None  # 图标 URL
    qty: int
    unit_price: int | None = None  # 铜；None=无价格
    price_source: str | None = None  # ah | npc | None
    line_cost: int | None = None  # qty * unit_price


class RecipeOut(BaseModel):
    id: int
    product_item_id: int | None
    product_name: str
    product_icon: str | None = None  # 成品图标 URL
    product_kind: str
    product_qty: int
    is_new: bool
    skill_orange: int
    skill_yellow: int
    skill_green: int
    skill_gray: int
    source_type: str
    source_item_id: int | None
    source_name: str | None = None
    materials: list[MaterialOut] = []
    # 计算派生（可能为 None 表示缺价格不可用）
    mat_cost: int | None = None
    revenue: int | None = None
    net_cost: int | None = None
    blocked: bool = False
    confirmed: bool = False


# ---------- 价格 ----------


class ImportSummaryOut(BaseModel):
    batch_id: int
    row_count: int
    matched: int
    unmatched: int
    inserted: int
    unmatched_names: list[str] = []


class EffectivePriceOut(BaseModel):
    item_id: int
    name: str
    icon: str | None = None  # 图标 URL
    price: int
    mode: str
    record_count: int
    last_at: datetime | None = None


class PriceHistoryPointOut(BaseModel):
    batch_id: int
    unit_price: int
    created_at: datetime | None = None
    imported_by: str | None = None


class ItemPriceOut(BaseModel):
    item_id: int
    name: str
    icon: str | None = None  # 图标 URL
    name_en: str | None = None
    quality: int = 0
    vendor_price: int = 0
    effective_ah: int | None = None
    effective_mode: str | None = None
    record_count: int = 0
    history: list[PriceHistoryPointOut] = []


class ManualPriceIn(BaseModel):
    server_id: int
    item_id: int
    unit_price: int = Field(ge=0)
    imported_by: str | None = None


# ---------- 路线计算 ----------


class CalcIn(BaseModel):
    server_id: int
    profession_key: str
    from_skill: int = Field(ge=0, le=375)
    to_skill: int = Field(ge=1, le=375)
    price_mode: PriceMode = "latest"
    product_disposition: Disposition = "sell_ah"
    blocked_recipe_ids: list[int] = []
    blocked_item_ids: list[int] = []
    confirmed_recipe_ids: list[int] = []
    include_designs: bool = True
    # 设计图获取方式：ah=AH 可购买，图纸价计入冲级成本；drop=掉落获得，不计成本
    design_cost: DesignCost = "ah"


class CalcStepOut(BaseModel):
    skill_from: int
    skill_to: int
    recipe_id: int
    recipe_name: str
    product_item_id: int | None
    product_icon: str | None = None  # 成品图标 URL
    crafts: int
    prob: float
    band: str  # orange | yellow | green
    mat_cost: int
    revenue: int
    net: int
    confirmed: bool
    source_type: str
    design_cost: int = 0  # 本段一次性设计图成本（铜，AH 购买时）
    design_name: str | None = None  # 设计图物品名


class MaterialTotalOut(BaseModel):
    item_id: int
    name: str
    icon: str | None = None  # 图标 URL
    qty: int
    unit_price: int | None
    price_source: str | None
    cost: int | None
    kind: str = "material"  # material | design


class CalcTotalsOut(BaseModel):
    crafts: int
    mat_cost: int
    revenue: int
    net: int
    net_display: str


class CalcOut(BaseModel):
    profession: dict
    server: dict
    params: dict
    steps: list[CalcStepOut] = []
    totals: CalcTotalsOut
    materials: list[MaterialTotalOut] = []
    warnings: list[str] = []
    excluded: list[dict] = []


# ---------- 保存/分享路线 ----------


class RouteSaveIn(BaseModel):
    server_id: int
    profession_key: str
    from_skill: int = Field(ge=0, le=375)
    to_skill: int = Field(ge=1, le=375)
    title: str = Field(min_length=1, max_length=160)
    author: str | None = Field(default=None, max_length=64)
    notes: str | None = None
    price_mode: PriceMode = "latest"
    product_disposition: Disposition = "sell_ah"
    blocked_recipe_ids: list[int] = []
    blocked_item_ids: list[int] = []
    confirmed_recipe_ids: list[int] = []
    include_designs: bool = True
    design_cost: DesignCost = "ah"
    is_public: bool = True


# ---------- 模板导出（AUC 关注清单） ----------


class WatchlistItemOut(BaseModel):
    item_id: int
    name: str
    icon: str | None = None  # 图标 URL
    kind: str  # material | product | design


class WatchlistOut(BaseModel):
    profession: dict
    list_name: str
    count: int
    items: list[WatchlistItemOut] = []
    text: str  # AUC 关注清单文本：清单名^物品1^物品2…


class RouteListItemOut(BaseModel):
    id: int
    share_code: str
    title: str
    author: str | None
    server_name: str
    profession_name: str
    profession_key: str
    from_skill: int
    to_skill: int
    price_mode: str
    net_display: str
    is_public: bool
    created_at: datetime | None = None

    model_config = {"from_attributes": True}


class RouteDetailOut(BaseModel):
    id: int
    share_code: str
    title: str
    author: str | None
    notes: str | None
    server: dict
    profession: dict
    params: dict
    steps: list[CalcStepOut] = []
    totals: CalcTotalsOut
    materials: list[MaterialTotalOut] = []
    warnings: list[str] = []
    is_public: bool
    created_at: datetime | None = None
