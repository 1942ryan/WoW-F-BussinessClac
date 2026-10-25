<script setup lang="ts">
/**
 * 金钱显示：金币/银币/铜币图标 + 数字。
 *
 * 图标来自 wowplayer.cc 的 .coin-gold/.coin-silver/.coin-copper（原生 13×13 GIF），
 * 以 base64 内联 —— 三个文件加起来不到 1 KB，省掉额外请求，且不会被缩放糊掉。
 * 之前用官方图库里的 JPG 缩到 13px，辨认度很差。
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

type CoinKind = "gold" | "silver" | "copper";

const parts = computed(() => {
  const v = props.value;
  if (v === null || v === undefined || !Number.isFinite(v)) return null;
  const neg = v < 0;
  const c = Math.abs(Math.round(v));
  const gold = Math.floor(c / 10000);
  const silver = Math.floor((c % 10000) / 100);
  const copper = c % 100;
  const out: { kind: CoinKind; n: number }[] = [];
  if (gold || props.showZero) out.push({ kind: "gold", n: gold });
  if (silver || props.showZero || out.length) out.push({ kind: "silver", n: silver });
  if (copper || props.showZero || !out.length) out.push({ kind: "copper", n: copper });
  return { neg, out };
});
</script>


<template>
  <span v-if="parts" class="money-ic" :style="{ fontSize: size + 2 + 'px' }">
    <span v-if="parts.neg && !negAsEarn" class="neg-sign">−</span>
    <span v-else-if="parts.neg && negAsEarn" class="earn-sign">赚</span>
    <span v-for="(p, i) in parts.out" :key="i" class="money-unit">
      <span class="coin" :class="'coin-' + p.kind" :style="{ width: size + 'px', height: size + 'px' }" />
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
  background-repeat: no-repeat;
  background-position: center;
  background-size: contain;
  /* 原生 13×13 缩到更小时用最近邻，避免发虚 */
  image-rendering: -webkit-optimize-contrast;
  image-rendering: pixelated;
  vertical-align: -2px;
}
.coin-gold { background-image: url(data:image/gif;base64,R0lGODlhDQANAPP/ACUjG4hzG9e4F+LWcKmLC15RH+jKOMGbHNK5RbCaMT01GMmoLOXgk//nSbeSFgAAACH+DGdpZjRqMTIxNCAgIAAh+QQFyAAPACwAAAAADQANAAMEWfDJB5QC+E5ciDtgoFHB4XzGciqkenrOIgSPIgjmoeoGAQSpD26BQMwACUMiRiwafQvDgIEYDIqyAKCQmDKsxR4GQBBUnUqWROFoGN4I0YRSKdgLgPlmrI8AADvShmCDMFwuD8MkQCgAEgME4jJ4RARSKBYcD3APDBIZPiIVGhgCAhIGMiMkJQCYAAWVKyiblSEAOw==); }
.coin-silver { background-image: url(data:image/gif;base64,R0lGODlhDQANAPP/ABISEiYmJjU1NUdHSFlZWWdnZ3Z2doaGhpaWlqmpqbW1tcTExNfX1wAAAAAAAAAAACH+DGdpZjRqMTIxNCAgIAAh+QQFyAAPACwAAAAADQANAAMEWvDJF2oVYcogSjlGMQBTMHgFghAGkQnHgRKoUaVyERq8PRwIkOeQQPAChGIPqDQIBggFI5FgLIoHVyDF6C4UsYOAJOApFsGEmLQhUhUJgUYiIAxOAfa8AshoIgA7zAExQGAkFUtiwTEYFB7zAVJyKjgcHhQHBw4VNRUSFwsdDwQDB4c2BHYGFAMTKyITEBERGQE1miQFGiorIQA7); }
.coin-copper { background-image: url(data:image/gif;base64,R0lGODlhDQANAPP/ACYeHIY7GbF1T08wINKqipdWM2Y+KbyLaaZnQXw7GIhHJceBT5VJINy8oaRcMQAAACH+DGdpZjRqMTIxNCAgIAAh+QQFyAAPACwAAAAADQANAAMEWvBJCaqdE4ygijIABnABszgJM0iDoyhBEpQF8wAKoiQK09cJgAHh+gkEQEAB6VkKDkmFgEAoHAgHAUJVsTYaWCQqJCwgsAiEABS6GQSLxROEkRgG90G7btlLIgA7y4VgIUAeulKHoPC0sbiYNDJpTyQIMDFHDBoYGBoFAYMoAQcMBweMMicoIQA7); }
.neg-sign {
  margin-right: 1px;
}
.earn-sign {
  margin-right: 2px;
  color: var(--red, #c62828);
  font-weight: 700;
}
</style>
