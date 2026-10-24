import axios from "axios";
import type {
  BatchInfo,
  CalcParams,
  CalcResult,
  EffectivePrice,
  ImportSummary,
  ItemPrice,
  Profession,
  Recipe,
  RouteDetail,
  RouteListItem,
  Server,
  Watchlist,
} from "@/types";

/** 统一走 /api 前缀，开发由 vite proxy 转发，生产由 nginx 转发。 */
const http = axios.create({
  baseURL: "/api/v1",
  timeout: 30000,
});

export const api = {
  // 服务器
  listServers: () => http.get<Server[]>("/servers").then((r) => r.data),
  createServer: (name: string) =>
    http.post<{ id: number; name: string; existed: boolean }>("/servers", { name }).then((r) => r.data),

  // 专业与配方
  listProfessions: () => http.get<Profession[]>("/professions").then((r) => r.data),
  listRecipes: (key: string, serverId: number, mode: string, disposition: string) =>
    http
      .get<Recipe[]>(`/professions/${key}/recipes`, {
        params: { server_id: serverId, price_mode: mode, disposition },
      })
      .then((r) => r.data),
  watchlist: (key: string, fromSkill?: number, toSkill?: number) =>
    http
      .get<Watchlist>(`/professions/${key}/watchlist`, {
        params: { from_skill: fromSkill, to_skill: toSkill },
      })
      .then((r) => r.data),

  // 价格
  importPrices: (file: File, serverId: number, importedBy: string) => {
    const fd = new FormData();
    fd.append("file", file);
    fd.append("server_id", String(serverId));
    if (importedBy) fd.append("imported_by", importedBy);
    return http.post<ImportSummary>("/prices/import", fd).then((r) => r.data);
  },
  importPricesText: (text: string, serverId: number, importedBy: string) => {
    const blob = new Blob([text], { type: "text/csv" });
    return api.importPrices(new File([blob], "pasted.csv"), serverId, importedBy);
  },
  manualPrice: (serverId: number, itemId: number, unitPrice: number, importedBy?: string) =>
    http
      .post<ImportSummary>("/prices/manual", {
        server_id: serverId,
        item_id: itemId,
        unit_price: unitPrice,
        imported_by: importedBy,
      })
      .then((r) => r.data),
  listBatches: (serverId: number) =>
    http.get<BatchInfo[]>("/prices/batches", { params: { server_id: serverId } }).then((r) => r.data),
  effectivePrices: (serverId: number, mode: string, q?: string) =>
    http
      .get<EffectivePrice[]>("/prices", { params: { server_id: serverId, mode, q, limit: 500 } })
      .then((r) => r.data),
  itemPrice: (itemId: number, serverId: number) =>
    http
      .get<ItemPrice>(`/prices/item/${itemId}`, { params: { server_id: serverId } })
      .then((r) => r.data),
  searchItems: (q: string) =>
    http
      .get<{ item_id: number; name: string; name_en: string | null; quality: number; vendor_price: number }[]>(
        "/items/search",
        { params: { q } }
      )
      .then((r) => r.data),

  // 路线
  calc: (params: CalcParams) => http.post<CalcResult>("/routes/calc", params).then((r) => r.data),
  saveRoute: (payload: CalcParams & { title: string; author?: string; notes?: string; is_public: boolean }) =>
    http.post<RouteDetail>("/routes", payload).then((r) => r.data),
  listRoutes: (params: { profession_key?: string; server_id?: number; public_only?: boolean }) =>
    http.get<RouteListItem[]>("/routes", { params }).then((r) => r.data),
  routeDetail: (shareCode: string) =>
    http.get<RouteDetail>(`/routes/${shareCode}`).then((r) => r.data),
  routeRecalc: (shareCode: string) =>
    http.post<CalcResult>(`/routes/${shareCode}/recalc`).then((r) => r.data),
};

export default http;
