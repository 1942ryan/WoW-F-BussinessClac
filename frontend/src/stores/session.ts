import { defineStore } from "pinia";
import { ref } from "vue";
import type { CalcParams, Disposition, Faction } from "@/types";

const LS_KEY = "wowfc-session-v2";

interface SessionState {
  serverId: number | null;
  serverName: string;
  /** 当前服务器阵营：alliance/horde/both（价格按阵营隔离） */
  serverFaction: Faction;
  professionKey: string;
  fromSkill: number;
  toSkill: number;
  priceMode: "latest" | "median";
  blockedRecipeIds: number[];
  blockedItemIds: number[];
  confirmedRecipeIds: number[];
  /** 确认配方的制作次数 {recipeId: count}，默认 1（长 CD 配方手填） */
  confirmedCounts: Record<string, number>;
  /** 单配方产物处置覆盖 {recipeId: 处置}，缺省跟随全局（全局固定为卖拍卖行） */
  recipeDispositions: Record<string, Disposition>;
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
    blockedRecipeIds: [],
    blockedItemIds: [],
    confirmedRecipeIds: [],
    confirmedCounts: {},
    recipeDispositions: {},
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
    state.value.blockedRecipeIds = [...p.blocked_recipe_ids];
    state.value.blockedItemIds = [...p.blocked_item_ids];
    state.value.confirmedRecipeIds = [...p.confirmed_recipe_ids];
    state.value.confirmedCounts = { ...(p.confirmed_counts ?? {}) };
    // 兼容旧路线里的 self_use 覆盖（该选项已下线）：丢弃，回落到默认卖拍卖行
    const disp: Record<string, Disposition> = {};
    for (const [k, v] of Object.entries(p.recipe_dispositions ?? {})) {
      if (v === "sell_ah" || v === "sell_npc") disp[k] = v;
    }
    state.value.recipeDispositions = disp;
    persist();
  }

  function toCalcParams(): CalcParams {
    return {
      server_id: state.value.serverId ?? 0,
      profession_key: state.value.professionKey,
      from_skill: state.value.fromSkill,
      to_skill: state.value.toSkill,
      price_mode: state.value.priceMode,
      blocked_recipe_ids: state.value.blockedRecipeIds,
      blocked_item_ids: state.value.blockedItemIds,
      confirmed_recipe_ids: state.value.confirmedRecipeIds,
      confirmed_counts: { ...state.value.confirmedCounts },
      recipe_dispositions: { ...state.value.recipeDispositions },
    };
  }

  return {
    state,
    persist,
    setServer,
    setProfession,
    setRange,
    setPriceMode,
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
