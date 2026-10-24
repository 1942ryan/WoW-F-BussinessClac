import { defineStore } from "pinia";
import { ref } from "vue";
import type { CalcParams, Disposition, Faction, ProbMode } from "@/types";

const LS_KEY = "wowfc-session-v1";

interface SessionState {
  serverId: number | null;
  serverName: string;
  /** 当前服务器阵营：alliance/horde/both（价格按阵营隔离） */
  serverFaction: Faction;
  professionKey: string;
  fromSkill: number;
  toSkill: number;
  priceMode: "latest" | "median";
  disposition: Disposition;
  includeDesigns: boolean;
  designCost: "ah" | "drop";
  blockedRecipeIds: number[];
  blockedItemIds: number[];
  confirmedRecipeIds: number[];
  /** 确认配方的制作次数 {recipeId: count}，默认 1（长 CD 配方手填） */
  confirmedCounts: Record<string, number>;
  /** 单配方产物处置覆盖 {recipeId: 处置}，缺省跟随全局 */
  recipeDispositions: Record<string, Disposition>;
  /** 涨点几率模型：formula=客户端公式；fixed=固定档位 */
  probMode: ProbMode;
  probOrange: number;
  probYellow: number;
  probGreen: number;
}

function load(): SessionState {
  try {
    const raw = localStorage.getItem(LS_KEY);
    if (raw) return { ...defaults(), ...(JSON.parse(raw) as Partial<SessionState>) };
  } catch {
    /* ignore */
  }
  return defaults();
}

function defaults(): SessionState {
  return {
    serverId: null,
    serverName: "",
    serverFaction: "both",
    professionKey: "",
    fromSkill: 1,
    toSkill: 75,
    priceMode: "latest",
    disposition: "sell_ah",
    includeDesigns: true,
    designCost: "ah",
    blockedRecipeIds: [],
    blockedItemIds: [],
    confirmedRecipeIds: [],
    confirmedCounts: {},
    recipeDispositions: {},
    probMode: "formula",
    probOrange: 100,
    probYellow: 50,
    probGreen: 25,
  };
}

export const useSessionStore = defineStore("session", () => {
  const state = ref<SessionState>(load());

  function persist() {
    localStorage.setItem(LS_KEY, JSON.stringify(state.value));
  }

  function setServer(id: number, name: string, faction: Faction = "both") {
    state.value.serverId = id;
    state.value.serverName = name;
    state.value.serverFaction = faction;
    persist();
  }

  function setProfession(key: string) {
    state.value.professionKey = key;
    persist();
  }

  function setRange(from: number, to: number) {
    state.value.fromSkill = from;
    state.value.toSkill = to;
    persist();
  }

  function setPriceMode(mode: "latest" | "median") {
    state.value.priceMode = mode;
    persist();
  }

  function setDisposition(d: Disposition) {
    state.value.disposition = d;
    persist();
  }

  function setIncludeDesigns(v: boolean) {
    state.value.includeDesigns = v;
    persist();
  }

  function setDesignCost(v: "ah" | "drop") {
    state.value.designCost = v;
    persist();
  }

  function setProbMode(m: ProbMode) {
    state.value.probMode = m;
    persist();
  }

  function setProb(kind: "orange" | "yellow" | "green", pct: number) {
    if (!Number.isFinite(pct)) return;
    const key = `prob${kind[0].toUpperCase()}${kind.slice(1)}` as "probOrange";
    state.value[key] = pct;
    persist();
  }

  function toggleBlockRecipe(id: number) {
    const arr = state.value.blockedRecipeIds;
    state.value.blockedRecipeIds = arr.includes(id) ? arr.filter((x) => x !== id) : [...arr, id];
    persist();
  }

  function toggleConfirmRecipe(id: number) {
    const arr = state.value.confirmedRecipeIds;
    state.value.confirmedRecipeIds = arr.includes(id) ? arr.filter((x) => x !== id) : [...arr, id];
    if (!state.value.confirmedRecipeIds.includes(id)) {
      delete state.value.confirmedCounts[String(id)];
    } else if (state.value.confirmedCounts[String(id)] === undefined) {
      state.value.confirmedCounts[String(id)] = 1; // 默认 1 次
    }
    persist();
  }

  function setConfirmedCount(id: number, count: number) {
    const n = Math.max(1, Math.round(count) || 1);
    state.value.confirmedCounts[String(id)] = n;
    persist();
  }

  function confirmedCountOf(id: number): number {
    return state.value.confirmedCounts[String(id)] ?? 1;
  }

  function setRecipeDisposition(id: number, d: Disposition | "") {
    if (d === "") {
      delete state.value.recipeDispositions[String(id)];
    } else {
      state.value.recipeDispositions[String(id)] = d;
    }
    persist();
  }

  function recipeDispositionOf(id: number): Disposition | "" {
    return state.value.recipeDispositions[String(id)] ?? "";
  }

  function toggleBlockItem(id: number) {
    const arr = state.value.blockedItemIds;
    state.value.blockedItemIds = arr.includes(id) ? arr.filter((x) => x !== id) : [...arr, id];
    persist();
  }

  function clearOverrides() {
    state.value.blockedRecipeIds = [];
    state.value.blockedItemIds = [];
    state.value.confirmedRecipeIds = [];
    state.value.confirmedCounts = {};
    persist();
  }

  function applyParams(p: CalcParams) {
    state.value.fromSkill = p.from_skill;
    state.value.toSkill = p.to_skill;
    state.value.priceMode = p.price_mode;
    state.value.disposition = p.product_disposition;
    state.value.includeDesigns = p.include_designs;
    state.value.designCost = p.design_cost ?? "ah";
    state.value.blockedRecipeIds = [...p.blocked_recipe_ids];
    state.value.blockedItemIds = [...p.blocked_item_ids];
    state.value.confirmedRecipeIds = [...p.confirmed_recipe_ids];
    state.value.confirmedCounts = { ...(p.confirmed_counts ?? {}) };
    state.value.recipeDispositions = { ...(p.recipe_dispositions ?? {}) };
    if (p.prob_mode) state.value.probMode = p.prob_mode;
    if (p.prob_orange != null) state.value.probOrange = p.prob_orange * 100;
    if (p.prob_yellow != null) state.value.probYellow = p.prob_yellow * 100;
    if (p.prob_green != null) state.value.probGreen = p.prob_green * 100;
    persist();
  }

  function toCalcParams(): CalcParams {
    return {
      server_id: state.value.serverId ?? 0,
      profession_key: state.value.professionKey,
      from_skill: state.value.fromSkill,
      to_skill: state.value.toSkill,
      price_mode: state.value.priceMode,
      product_disposition: state.value.disposition,
      blocked_recipe_ids: state.value.blockedRecipeIds,
      blocked_item_ids: state.value.blockedItemIds,
      confirmed_recipe_ids: state.value.confirmedRecipeIds,
      confirmed_counts: { ...state.value.confirmedCounts },
      recipe_dispositions: { ...state.value.recipeDispositions },
      include_designs: state.value.includeDesigns,
      design_cost: state.value.designCost,
      prob_mode: state.value.probMode,
      prob_orange: state.value.probOrange / 100,
      prob_yellow: state.value.probYellow / 100,
      prob_green: state.value.probGreen / 100,
    };
  }

  return {
    state,
    persist,
    setServer,
    setProfession,
    setRange,
    setPriceMode,
    setDisposition,
    setIncludeDesigns,
    setDesignCost,
    setProbMode,
    setProb,
    toggleBlockRecipe,
    toggleConfirmRecipe,
    setConfirmedCount,
    confirmedCountOf,
    setRecipeDisposition,
    recipeDispositionOf,
    toggleBlockItem,
    clearOverrides,
    applyParams,
    toCalcParams,
  };
});
