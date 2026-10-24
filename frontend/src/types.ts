/** API 类型定义（与后端 Pydantic Schema 对应）。 */

export interface Server {
  id: number;
  name: string;
  batch_count: number;
  route_count: number;
  created_at?: string;
}

export interface Profession {
  id: number;
  key: string;
  name: string;
  recipe_count: number;
  max_skill: number;
}

export interface MaterialLine {
  item_id: number;
  name: string;
  qty: number;
  unit_price: number | null;
  price_source: "ah" | "npc" | null;
  line_cost: number | null;
}

export interface Recipe {
  id: number;
  product_item_id: number | null;
  product_name: string;
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
  price: number;
  mode: string;
  record_count: number;
  last_at: string | null;
}

export interface ItemPrice {
  item_id: number;
  name: string;
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
  crafts: number;
  prob: number;
  band: string;
  mat_cost: number;
  revenue: number;
  net: number;
  confirmed: boolean;
  source_type: string;
}

export interface MaterialTotal {
  item_id: number;
  name: string;
  qty: number;
  unit_price: number | null;
  price_source: string | null;
  cost: number | null;
}

export interface CalcTotals {
  crafts: number;
  mat_cost: number;
  revenue: number;
  net: number;
  net_display: string;
}

export interface CalcParams {
  server_id: number;
  profession_key: string;
  from_skill: number;
  to_skill: number;
  price_mode: "latest" | "median";
  product_disposition: "sell_ah" | "sell_npc" | "self_use";
  blocked_recipe_ids: number[];
  blocked_item_ids: number[];
  confirmed_recipe_ids: number[];
  include_designs: boolean;
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

export interface RouteListItem {
  id: number;
  share_code: string;
  title: string;
  author: string | null;
  server_name: string;
  profession_name: string;
  profession_key: string;
  from_skill: number;
  to_skill: number;
  price_mode: string;
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
  server: { id: number; name: string };
  profession: { key: string; name: string };
  params: CalcParams;
  steps: CalcStep[];
  totals: CalcTotals;
  materials: MaterialTotal[];
  warnings: string[];
  is_public: boolean;
  created_at: string | null;
}
