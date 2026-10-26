<script lang="ts">
/** 模块级自增：保证每个组件实例的渐变 id 唯一（<script setup> 里的顶层代码是「每实例执行」，不能用来计数） */
let uidSeq = 0;
export function nextCoinUid(): string {
  return `coin${++uidSeq}`;
}
</script>

<script setup lang="ts">
/**
 * 金钱显示：数字 + 金币/银币/铜币图标（顺序同游戏内：先数字后图标，如「1金87银58铜」）。
 *
 * 图标走内联 SVG（矢量）而不是位图：
 * - 游戏原生贴图只有 16×16（UI-GoldIcon / UI-SilverIcon / UI-CopperIcon），
 *   在 1080P 缩放到 13px 再被系统缩放会出现锯齿/发糊，之前用的 13×13 GIF 更明显；
 * - 矢量按当前 DPI 实时绘制，13px 与 26px 都锐利，且只有几百字节、无需网络请求。
 * 配色取自游戏原生贴图中心像素：金 #d8c14d / 银 #9a999a / 铜 #ac714c。
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

/** 渐变 id 必须唯一，否则同页面多个实例会互相覆盖（Safari 尤其明显） */
const uid = nextCoinUid();

// 中心亮 → 边缘暗，模拟游戏里带弧面的金属圆片
const PALETTE: Record<CoinKind, { rim: string; hi: string; mid: string; lo: string }> = {
  gold: { rim: "#6a4f0f", hi: "#fdf3ad", mid: "#d8c14d", lo: "#8a6a13" },
  silver: { rim: "#46454a", hi: "#f4f3f5", mid: "#adacb0", lo: "#67666b" },
  copper: { rim: "#572c14", hi: "#eab48a", mid: "#ac714c", lo: "#6b3819" },
};
</script>

<template>
  <span v-if="parts" class="money-ic" :style="{ fontSize: size + 2 + 'px' }">
    <span v-if="parts.neg && !negAsEarn" class="neg-sign">−</span>
    <span v-else-if="parts.neg && negAsEarn" class="earn-sign">赚</span>
    <span v-for="(p, i) in parts.out" :key="i" class="money-unit">
      <span class="money-num">{{ p.n }}</span>
      <svg
        class="coin"
        :width="size"
        :height="size"
        viewBox="0 0 16 16"
        aria-hidden="true"
        focusable="false"
      >
        <defs>
          <radialGradient :id="uid + p.kind + i" cx="36%" cy="28%" r="80%">
            <stop offset="0%" :stop-color="PALETTE[p.kind].hi" />
            <stop offset="48%" :stop-color="PALETTE[p.kind].mid" />
            <stop offset="100%" :stop-color="PALETTE[p.kind].lo" />
          </radialGradient>
        </defs>
        <circle cx="8" cy="8" r="7.1" :fill="PALETTE[p.kind].rim" />
        <circle cx="8" cy="8" r="6.05" :fill="`url(#${uid}${p.kind}${i})`" />
        <ellipse
          cx="6.1"
          cy="5.05"
          rx="1.95"
          ry="1.1"
          fill="#fff"
          opacity="0.45"
          transform="rotate(-28 6.1 5.05)"
        />
      </svg>
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
  margin-left: 1px;
  flex: none;
  /* 矢量图形，浏览器按设备像素比绘制，不需要 pixelated */
  vertical-align: -2px;
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
