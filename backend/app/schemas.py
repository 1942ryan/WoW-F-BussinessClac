"""Pydantic 请求/响应模型。"""

from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field

PriceMode = Literal["latest", "median"]
Disposition = Literal["sell_ah", "sell_npc", "self_use"]
DesignCost = Literal["ah", "drop"]
ProbMode = Literal["formula", "fixed"]
Faction = Literal["alliance", "horde", "both"]


# ---------- 通用 ----------


class OkOut(BaseModel):
    ok: bool = True
    message: str = ""


# ---------- 服务器 ----------


class ServerIn(BaseModel):
    name: str = Field(min_length=1, max_length=64)
    faction: Faction = "both"


class ServerOut(BaseModel):
    id: int
    name: str
    faction: str = "both"
    batch_count: int = 0
    route_count: int = 0
    created_at: datetime | None = None

    model_config = {"from_attributes": True}


class ServerCreatedOut(BaseModel):
    id: int
    name: str
    faction: str = "both"
    existed: bool


# ---------- 专业与配方 ----------


class ProfessionOut(BaseModel):
    id: int
    key: str
    name: str
    icon: str | None = None  # 图标 URL
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


class VendorCampOut(BaseModel):
    """贸易营地信息（联盟=艾泽拉斯贸易局 / 部落=杜隆塔尔补给后勤部）。"""

    camp: str  # 营地名，如「艾泽拉斯贸易局」
    npc: str  # 该阵营的配方商人 NPC
    zone: str  # 所在区域，如「赤脊山 · 三角路口」
    coord: str  # 坐标，如「10.2,72.5」
    crate_npc: str = ""  # 交板条箱换青睐的 NPC
    side: str = ""  # alliance / horde


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
    # 产物双价格（单次产出，铜）：卖店价 / 拍卖行有效价（无流水为 None）
    product_npc_price: int | None = None
    product_ah_price: int | None = None
    # 成品在拍卖行查不到价格 → 收入已回退按 NPC 卖店价估算（多为冷门配方，提示用户自行判断）
    revenue_fallback: bool = False
    # 来源详情（悬停展示）：训练师标明可学等级；设计图标明图纸名与拍卖行/卖店价
    source_detail: str | None = None
    # 贸易营地专属图纸：需要「商人青睐」点数（非声望），null = 不是营地配方
    vendor_favor: int | None = None
    # 营地质询信息（两个阵营的营地/NPC/坐标），按服务器阵营取对应一侧
    vendor_camp: VendorCampOut | None = None


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
    # 确认配方的制作次数 {recipe_id: count}；未列出的确认配方默认 1 次
    confirmed_counts: dict[int, int] = {}
    # 单配方产物处置覆盖 {recipe_id: sell_ah|sell_npc|self_use}；未列出的跟随全局
    recipe_dispositions: dict[int, Disposition] = {}
    include_designs: bool = True
    # 设计图获取方式：ah=AH 可购买，图纸价计入冲级成本；drop=掉落获得，不计成本
    design_cost: DesignCost = "ah"
    # 涨点几率模型：formula=客户端公式 (灰档-当前)/(灰档-黄档)；fixed=固定档位
    prob_mode: ProbMode = "formula"
    # fixed 模式下的档位几率（0~1），缺省用服务端配置（橙100/黄50/绿25）
    prob_orange: float | None = Field(default=None, ge=0, le=1)
    prob_yellow: float | None = Field(default=None, ge=0, le=1)
    prob_green: float | None = Field(default=None, ge=0, le=1)


class CalcStepOut(BaseModel):
    skill_from: int
    skill_to: int
    recipe_id: int
    recipe_name: str
    product_item_id: int | None
    product_icon: str | None = None  # 成品图标 URL
    crafts: float  # 期望制作次数（公式模式可能是小数，展示时取整）
    prob: float
    prob_end: float | None = None  # 段末几率（公式模式下与 prob 不同）
    band: str  # orange | yellow | green
    disposition: str | None = None  # 本段产物处置
    mat_cost: float
    revenue: float
    net: float
    confirmed: bool
    source_type: str
    design_cost: int = 0  # 本段一次性设计图成本（铜，AH 购买时）
    design_name: str | None = None  # 设计图物品名
    revenue_fallback: bool = False  # 本段成品拍卖行无价 → 收入按 NPC 卖店价估算
    vendor_favor: int = 0  # 本段图纸来自贸易营地，需「商人青睐」点数（非声望）


class MaterialTotalOut(BaseModel):
    item_id: int
    name: str
    icon: str | None = None  # 图标 URL
    qty: float
    unit_price: int | None
    price_source: str | None
    cost: float | None
    kind: str = "material"  # material | design


class CalcTotalsOut(BaseModel):
    crafts: float
    mat_cost: float
    revenue: float
    net: float
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
    confirmed_counts: dict[int, int] = {}
    recipe_dispositions: dict[int, Disposition] = {}
    include_designs: bool = True
    design_cost: DesignCost = "ah"
    prob_mode: ProbMode = "formula"
    prob_orange: float | None = Field(default=None, ge=0, le=1)
    prob_yellow: float | None = Field(default=None, ge=0, le=1)
    prob_green: float | None = Field(default=None, ge=0, le=1)
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


# ---------- 物品详情（图标悬停 tooltip 用） ----------


class ItemDetailOut(BaseModel):
    item_id: int
    name: str
    name_en: str | None = None
    quality: int = 0
    item_level: int | None = None
    type: str | None = None
    status: str | None = None
    icon: str | None = None
    vendor_price: int = 0  # 卖店价（铜）
    effective_ah: int | None = None  # 当前服务器拍卖行有效价（铜）
    record_count: int = 0  # 价格流水条数


class RouteListItemOut(BaseModel):
    id: int
    share_code: str
    title: str
    author: str | None
    server_name: str
    server_faction: str = "both"
    profession_name: str
    profession_key: str
    from_skill: int
    to_skill: int
    price_mode: str
    net: float = 0
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
