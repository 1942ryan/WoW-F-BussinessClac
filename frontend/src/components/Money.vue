<script setup lang="ts">
/**
 * 金钱显示：金币/银币/铜币图标 + 数字（替代纯文本「1金23银4铜」）。
 * 图标为内嵌 SVG，任意尺寸清晰、无外部请求；零值单位省略（与游戏内一致）。
 */
import { computed, useId } from "vue";

const props = withDefaults(
  defineProps<{
    value: number | null | undefined;
    /** 是否显示 0 值单位（默认省略，与 WoW 金钱框架一致） */
    showZero?: boolean;
    size?: number;
  }>(),
  { value: null, showZero: false, size: 13 }
);

const uid = useId().replace(/[^a-zA-Z0-9]/g, "");

interface CoinDef {
  key: string;
  light: string;
  mid: string;
  dark: string;
  rim: string;
}

const COINS: Record<string, CoinDef> = {
  gold: { key: "g", light: "#fbe38b", mid: "#e8b53a", dark: "#a67c17", rim: "#7a5a10" },
  silver: { key: "s", light: "#f4f6f8", mid: "#c3cad2", dark: "#8b95a1", rim: "#5f6873" },
  copper: { key: "c", light: "#f0b48a", mid: "#c9713c", dark: "#8f4a20", rim: "#63320f" },
};

function coinSvg(c: CoinDef) {
  const gid = `${uid}${c.key}`;
  return (
    `<svg viewBox="0 0 24 24" width="${props.size}" height="${props.size}" aria-hidden="true">` +
    `<defs><radialGradient id="${gid}" cx="38%" cy="32%" r="75%">` +
    `<stop offset="0%" stop-color="${c.light}"/><stop offset="55%" stop-color="${c.mid}"/>` +
    `<stop offset="100%" stop-color="${c.dark}"/></radialGradient></defs>` +
    `<circle cx="12" cy="12" r="10.5" fill="url(#${gid})" stroke="${c.rim}" stroke-width="1.4"/>` +
    `<circle cx="12" cy="12" r="7" fill="none" stroke="${c.light}" stroke-width="1" opacity="0.75"/>` +
    `<ellipse cx="9" cy="8" rx="3.4" ry="2.2" fill="#ffffff" opacity="0.35"/>` +
    `</svg>`
  );
}

const goldSvg = computed(() => coinSvg(COINS.gold));
const silverSvg = computed(() => coinSvg(COINS.silver));
const copperSvg = computed(() => coinSvg(COINS.copper));

const parts = computed(() => {
  const v = props.value;
  if (v === null || v === undefined || !Number.isFinite(v)) return null;
  const neg = v < 0;
  const c = Math.abs(Math.round(v));
  const gold = Math.floor(c / 10000);
  const silver = Math.floor((c % 10000) / 100);
  const copper = c % 100;
  const out: { icon: string; n: number }[] = [];
  if (gold || props.showZero) out.push({ icon: goldSvg.value, n: gold });
  if (silver || props.showZero || out.length) out.push({ icon: silverSvg.value, n: silver });
  if (copper || props.showZero || !out.length) out.push({ icon: copperSvg.value, n: copper });
  return { neg, out };
});
</script>

<template>
  <span v-if="parts" class="money-ic" :style="{ fontSize: size + 2 + 'px' }">
    <span v-if="parts.neg" class="neg-sign">−</span>
    <span v-for="(p, i) in parts.out" :key="i" class="money-unit">
      <span class="coin" v-html="p.icon" />
      <span class="money-num">{{ p.n }}</span>
    </span>
  </span>
  <span v-else class="muted">—</span>
</template>

<style scoped>
.money-ic {
  display: inline-flex;
  align-items: center;
  gap: 1px;
  white-space: nowrap;
  font-variant-numeric: tabular-nums;
  line-height: 1;
}
.money-unit {
  display: inline-flex;
  align-items: center;
  gap: 1px;
  margin-right: 3px;
}
.money-unit:last-child {
  margin-right: 0;
}
.coin {
  display: inline-flex;
  margin-right: 1px;
}
.coin :deep(svg) {
  display: block;
}
.neg-sign {
  margin-right: 1px;
}
</style>
