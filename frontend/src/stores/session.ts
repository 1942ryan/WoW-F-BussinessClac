import { defineStore } from "pinia";
import { ref } from "vue";
import type { CalcParams } from "@/types";

const LS_KEY = "wowfc-session-v1";

interface SessionState {
  serverId: number | null;
  serverName: string;
  professionKey: string;
  fromSkill: number;
  toSkill: number;
  priceMode: "latest" | "median";
  disposition: "sell_ah" | "sell_npc" | "self_use";
  includeDesigns: boolean;
  designCost: "ah" | "drop";
  blockedRecipeIds: number[];
  blockedItemIds: number[];
  confirmedRecipeIds: number[];
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
  };
}

export const useSessionStore = defineStore("session", () => {
  const state = ref<SessionState>(load());

  function persist() {
    localStorage.setItem(LS_KEY, JSON.stringify(state.value));
  }

  function setServer(id: number, name: string) {
    state.value.serverId = id;
    state.value.serverName = name;
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

  function setDisposition(d: "sell_ah" | "sell_npc" | "self_use") {
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

  function toggleBlockRecipe(id: number) {
    const arr = state.value.blockedRecipeIds;
    state.value.blockedRecipeIds = arr.includes(id) ? arr.filter((x) => x !== id) : [...arr, id];
    persist();
  }

  function toggleConfirmRecipe(id: number) {
    const arr = state.value.confirmedRecipeIds;
    state.value.confirmedRecipeIds = arr.includes(id) ? arr.filter((x) => x !== id) : [...arr, id];
    persist();
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
      include_designs: state.value.includeDesigns,
      design_cost: state.value.designCost,
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
    toggleBlockRecipe,
    toggleConfirmRecipe,
    toggleBlockItem,
    clearOverrides,
    applyParams,
    toCalcParams,
  };
});
