<script setup lang="ts">
/**
 * 金钱显示：WoW 原版货币图标（无限官方图标库 inv_misc_coin_*）+ 数字，
 * 替代纯文本「1金23银4铜」。零值单位省略（与游戏内金钱框架一致）。
 */
import { computed } from "vue";

const props = withDefaults(
  defineProps<{
    value: number | null | undefined;
    /** 是否显示 0 值单位（默认省略，与 WoW 金钱框架一致） */
    showZero?: boolean;
    size?: number;
    /** 负值渲染为红色「赚」前缀（而非负号）——用于成本列：负数=这次是赚钱的 */
    negAsEarn?: boolean;
  }>(),
  { value: null, showZero: false, size: 13, negAsEarn: false }
);

const CDN = "https://wowforever.wclbox.com/tubiao";
const COINS = {
  gold: `${CDN}/inv_misc_coin_01.jpg`,
  silver: `${CDN}/inv_misc_coin_02.jpg`,
  copper: `${CDN}/inv_misc_coin_05.jpg`,
};

const parts = computed(() => {
  const v = props.value;
  if (v === null || v === undefined || !Number.isFinite(v)) return null;
  const neg = v < 0;
  const c = Math.abs(Math.round(v));
  const gold = Math.floor(c / 10000);
  const silver = Math.floor((c % 10000) / 100);
  const copper = c % 100;
  const out: { icon: string; n: number }[] = [];
  if (gold || props.showZero) out.push({ icon: COINS.gold, n: gold });
  if (silver || props.showZero || out.length) out.push({ icon: COINS.silver, n: silver });
  if (copper || props.showZero || !out.length) out.push({ icon: COINS.copper, n: copper });
  return { neg, out };
});
</script>

<template>
  <span v-if="parts" class="money-ic" :style="{ fontSize: size + 2 + 'px' }">
    <span v-if="parts.neg && !negAsEarn" class="neg-sign">−</span>
    <span v-else-if="parts.neg && negAsEarn" class="earn-sign">赚</span>
    <span v-for="(p, i) in parts.out" :key="i" class="money-unit">
      <img class="coin" :src="p.icon" :width="size" :height="size" alt="" loading="lazy" decoding="async" />
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
  display: inline-block;
  margin-right: 1px;
  flex: none;
}
.neg-sign {
  margin-right: 1px;
}
.earn-sign {
  margin-right: 2px;
  color: var(--red, #c62828);
  font-weight: 700;
}
</style>
