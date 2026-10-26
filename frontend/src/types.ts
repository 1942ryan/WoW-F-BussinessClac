/** API 类型定义（与后端 Pydantic Schema 对应）。 */

export type Faction = "alliance" | "horde" | "both";

export interface Server {
  id: number;
  name: string;
  faction?: Faction;
  batch_count: number;
  route_count: number;
  created_at?: string;
}

export interface ItemDetail {
  item_id: number;
  name: string;
  name_en?: string | null;
  quality: number;
  item_level: number | null;
  type: string | null;
  status?: string | null;
  icon?: string | null;
  vendor_price: number;
  effective_ah: number | null;
  record_count: number;
  /** 这条拍卖价是哪次导入的（ISO 时间）、距今几小时、是否已超有效期 */
  price_updated_at?: string | null;
  price_age_hours?: number | null;
  price_stale?: boolean;
  price_valid_hours?: number;
  /** 游戏内 tooltip 全文（逐行）：绑定/部位/护甲值/属性/装备效果/售价 */
  tooltip: string[];
}

export interface Profession {
  id: number;
  key: string;
  name: string;
  icon?: string | null;
  recipe_count: number;
  max_skill: number;
}

export interface MaterialLine {
  item_id: number;
  name: string;
  icon?: string | null;
  qty: number;
  unit_price: number | null;
  price_source: "ah" | "npc" | null;
  line_cost: number | null;
  npc_limited?: boolean;
}

export interface Recipe {
  id: number;
  product_item_id: number | null;
  product_name: string;
  product_icon?: string | null;
  product_kind: "item" | "enchant";
  product_qty: number;
  is_new: boolean;
  skill_orange: number;
  skill_yellow: number;
  skill_green: number;
  skill_gray: number;
  source_type: string;
  source_item_id: number | null;
  source_name?: string | null;
  materials: MaterialLine[];
  mat_cost: number | null;
  revenue: number | null;
  net_cost: number | null;
  blocked: boolean;
  confirmed: boolean;
  /** 产物双价格（单次产出，铜）：卖店价 / 拍卖行有效价（无流水为 null） */
  product_npc_price: number | null;
  product_ah_price: number | null;
  /** 拍卖行到手价（已扣手续费，单次产出） */
  product_ah_net?: number | null;
  /** 成品拍卖行查不到价格 → 收入按卖店价估算（冷门信号，可手动屏蔽） */
  revenue_fallback: boolean;
  /** 拍卖行有价但到手价不如卖店 → 收入已自动按卖店价计 */
  revenue_npc_better?: boolean;
  /** 有冷却时间（CD）：确认采用时默认次数 1，其余默认不限 */
  has_cooldown?: boolean;
  /** 来源详情（悬停展示，\n 分行）：训练师可学等级 / 设计图名与拍卖行·卖店价 */
  source_detail?: string | null;
  /** 贸易营地专属图纸所需的「商人青睐」点数（非声望）；null = 不是营地配方 */
  vendor_favor?: number | null;
  /** 按服务器阵营给出的营地信息（联盟=艾泽拉斯贸易局 / 部落=杜隆塔尔补给后勤部） */
  vendor_camp?: VendorCamp | null;
}

/** 贸易营地信息 */
export interface VendorCamp {
  camp: string;
  npc: string;
  zone: string;
  coord: string;
  crate_npc: string;
  side: "alliance" | "horde" | "";
}

export interface ImportSummary {
  batch_id: number;
  row_count: number;
  matched: number;
  unmatched: number;
  inserted: number;
  unmatched_names: string[];
}

export interface BatchInfo {
  id: number;
  filename: string | null;
  source: string;
  row_count: number;
  matched: number;
  unmatched: number;
  imported_by: string | null;
  created_at: string;
}

export interface EffectivePrice {
  item_id: number;
  name: string;
  icon?: string | null;
  price: number;
  mode: string;
  record_count: number;
  last_at: string | null;
}

/** 云价格新鲜度：本服最近一次导入时间 + 过期物品数（有效期默认 24 小时）。 */
export interface PriceFreshness {
  server_id: number;
  server_name: string | null;
  last_import_at: string | null;
  age_hours: number | null;
  batch_count: number;
  item_count: number;
  stale_items: number;
  oldest_age_hours: number | null;
  last_imported_by: string | null;
  valid_hours: number;
  stale: boolean;
}

export interface ItemPrice {
  item_id: number;
  name: string;
  icon?: string | null;
  name_en: string | null;
  quality: number;
  vendor_price: number;
  effective_ah: number | null;
  effective_mode: string | null;
  record_count: number;
  history: { batch_id: number; unit_price: number; created_at: string; imported_by: string | null }[];
}

export interface CalcStep {
  skill_from: number;
  skill_to: number;
  recipe_id: number;
  recipe_name: string;
  product_item_id: number | null;
  product_icon?: string | null;
  crafts: number;
  prob: number;
  prob_end?: number | null;
  band: string;
  disposition?: string | null;
  mat_cost: number;
  revenue: number;
  /** 本步被拍卖行抽走的手续费（铜）；revenue 已扣除此项 */
  ah_cut?: number;
  net: number;
  confirmed: boolean;
  source_type: string;
  design_cost: number;
  design_name: string | null;
  /** 成品拍卖行无价 → 本步收入按卖店价估算 */
  revenue_fallback?: boolean;
  /** 收入口径：ah=拍卖行到手价 / npc=卖店价 / none=自用 */
  revenue_source?: "ah" | "npc" | "none";
  /** 拍卖行有价但到手价不如卖店 → 本步已按卖店价计 */
  revenue_npc_better?: boolean;
  /** 本步图纸来自贸易营地，需「商人青睐」点数（非声望） */
  vendor_favor?: number;
}

export interface MaterialTotal {
  item_id: number;
  name: string;
  icon?: string | null;
  qty: number;
  unit_price: number | null;
  price_source: string | null;
  cost: number | null;
  kind?: string;
  npc_limited?: boolean;
}

export interface CalcTotals {
  crafts: number;
  mat_cost: number;
  revenue: number;
  /** 拍卖行抽走的 5% 手续费（铜）；revenue 已扣除此项 */
  ah_cut: number;
  ah_cut_rate: number;
  net: number;
  net_display: string;
}

export type Disposition = "sell_ah" | "sell_npc";
export type ProbMode = "formula" | "fixed";

export interface CalcParams {
  server_id: number;
  profession_key: string;
  from_skill: number;
  to_skill: number;
  price_mode: "latest" | "median";
  /** 全局成品处置（固定为卖拍卖行；单配方可在配方列表覆盖） */
  product_disposition?: Disposition;
  blocked_recipe_ids: number[];
  blocked_item_ids: number[];
  confirmed_recipe_ids: number[];
  confirmed_counts?: Record<string, number>;
  recipe_dispositions?: Record<string, Disposition>;
}

export interface CalcResult {
  profession: { key: string; name: string };
  server: { id: number; name?: string };
  params: CalcParams;
  steps: CalcStep[];
  totals: CalcTotals;
  materials: MaterialTotal[];
  warnings: string[];
  excluded: { recipe_id: number; name: string; reason: string }[];
}

export interface WatchlistItem {
  item_id: number;
  name: string;
  icon?: string | null;
  kind: "material" | "product" | "design";
}

export interface Watchlist {
  profession: { key: string; name: string };
  list_name: string;
  count: number;
  items: WatchlistItem[];
  text: string;
}

export interface RouteListItem {
  id: number;
  share_code: string;
  title: string;
  author: string | null;
  server_name: string;
  server_faction?: Faction;
  profession_name: string;
  profession_key: string;
  from_skill: number;
  to_skill: number;
  price_mode: string;
  net: number;
  net_display: string;
  is_public: boolean;
  created_at: string | null;
}

export interface RouteDetail {
  id: number;
  share_code: string;
  title: string;
  author: string | null;
  notes: string | null;
  server: { id: number; name: string; faction?: Faction };
  profession: { key: string; name: string };
  params: CalcParams;
  steps: CalcStep[];
  totals: CalcTotals;
  materials: MaterialTotal[];
  warnings: string[];
  is_public: boolean;
  created_at: string | null;
}
