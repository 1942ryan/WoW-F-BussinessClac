<script setup lang="ts">
/**
 * 配方来源详情浮层（悬停「来源」列弹出）。
 * 内容来自后端 RecipeOut.source_detail（纯文本，\n 分行），这里做二次排版：
 *
 *   设计图：结构图：机械松鼠
 *   拍卖行：3银
 *   出处  出没地图  洛克莫丹、贫瘠之地、赤脊山
 *         ↳ 这些地图里的怪物/箱子能开出来（官方只精确到地图，不写具体 NPC 与掉率）
 *
 * 「出处」一行的官方原始文案是「训练师 / 商人 · X / 世界掉落 · 怪物 N 级 /
 * 掉落 · NPC · 地图 3% / 任务 · X / 出没 · 地图列表 / 开启 容器」，
 * 直接用会让人看不懂「出没」到底是不是掉落，所以这里翻成人话并补一句注解。
 * 与 ItemTooltip 一致：Teleport 到 body + fixed 定位，避免被表格滚动容器裁剪。
 */
import { computed, ref, watch } from "vue";

const props = withDefaults(
  defineProps<{
    text: string | null;
    visible: boolean;
    anchor: HTMLElement | null;
  }>(),
  { text: null, visible: false, anchor: null }
);

const pos = ref({ left: 0, top: 0 });

/** 官方来源标签 → 人话标签 + 一句注解（顺序有意义：「世界掉落」要先于「掉落」） */
const LABELS: { key: string; label: string; hint?: string }[] = [
  { key: "训练师", label: "训练师", hint: "找本专业训练师直接学" },
  { key: "商人", label: "商人出售", hint: "NPC 定点出售，价格固定" },
  { key: "世界掉落", label: "世界掉落", hint: "该等级段的怪物都可能掉，概率很低" },
  { key: "掉落", label: "怪物掉落", hint: "指定怪物掉落，后面的百分比是掉率" },
  { key: "任务", label: "任务奖励", hint: "做对应任务获得；[联] / [部] 是阵营限定" },
  {
    key: "出没",
    label: "出没地图",
    hint: "这张配方在这些地图的怪物 / 箱子里能开出来（官方只精确到地图，不写具体 NPC 和掉率）",
  },
  { key: "开启", label: "开箱获得", hint: "开这种容器有几率得到" },
];

interface Seg {
  label: string;
  detail: string;
  hint?: string;
}

function parseSegments(raw: string): Seg[] {
  return raw
    .split(/[；;]/)
    .map((s) => s.trim())
    .filter(Boolean)
    .map((s) => {
      for (const m of LABELS) {
        if (s.startsWith(m.key)) {
          const detail = s.slice(m.key.length).replace(/^[\s·:：]+/, "");
          return { label: m.label, detail, hint: m.hint };
        }
      }
      return { label: "", detail: s };
    });
}

const lines = computed(() =>
  (props.text ?? "")
    .split("\n")
    .map((l) => l.trim())
    .filter((l) => l !== "")
);

const title = computed(() => lines.value[0] ?? "");

/** 「出处：xxx」单独拎出来做成标签行 */
const sourceLine = computed(() => lines.value.slice(1).find((l) => l.startsWith("出处：")) ?? "");
const sourceSegs = computed(() => (sourceLine.value ? parseSegments(sourceLine.value.slice(3)) : []));

/** 其它普通行（拍卖行 / 卖店 / 商人青睐 / 位置…） */
const plainRows = computed(() => lines.value.slice(1).filter((l) => !l.startsWith("出处：")));

/** 本浮层里出现的标签说明（只列用得到的，避免每次都长篇大论） */
const hints = computed(() => {
  const out: string[] = [];
  for (const s of sourceSegs.value) {
    if (s.hint && !out.includes(s.hint)) out.push(s.hint);
  }
  return out;
});

function place() {
  const el = props.anchor;
  if (!el) return;
  const r = el.getBoundingClientRect();
  const w = 360;
  let left = r.right + 10;
  if (left + w > window.innerWidth - 8) left = Math.max(8, r.left - w - 10);
  let top = r.bottom + 6;
  // 高度未知，先按 200 估算；超出视口底部则翻到上方
  if (top + 200 > window.innerHeight - 8) top = Math.max(8, r.top - 206);
  pos.value = { left, top };
}

watch(
  () => props.visible,
  (v) => {
    if (v) requestAnimationFrame(place);
  }
);
</script>

<template>
  <Teleport to="body">
    <div v-if="visible && text" class="src-tip" :style="{ left: pos.left + 'px', top: pos.top + 'px' }">
      <div class="tip-title">{{ title }}</div>
      <div v-for="(line, i) in plainRows" :key="'p' + i" class="tip-row">{{ line }}</div>

      <template v-if="sourceSegs.length">
        <div class="src-head">出处</div>
        <div v-for="(s, i) in sourceSegs" :key="'s' + i" class="src-seg">
          <span v-if="s.label" class="src-label">{{ s.label }}</span>
          <span class="src-detail">{{ s.detail }}</span>
        </div>
        <div v-for="(h, i) in hints" :key="'h' + i" class="src-hint">↳ {{ h }}</div>
      </template>
    </div>
  </Teleport>
</template>

<style scoped>
.src-tip {
  position: fixed;
  z-index: 210;
  width: 360px;
  max-width: calc(100vw - 16px);
  padding: 8px 11px;
  background: rgba(18, 16, 12, 0.985);
  border: 1px solid #6b5a35;
  border-radius: 6px;
  box-shadow: 0 6px 24px rgba(0, 0, 0, 0.55);
  color: #e8e2d0;
  font-size: 12.5px;
  line-height: 1.65;
  pointer-events: none;
}
.tip-title {
  font-weight: 700;
  margin-bottom: 2px;
}
.tip-row {
  color: #c9c0a6;
}
.src-head {
  margin-top: 5px;
  padding-top: 5px;
  border-top: 1px dashed rgba(255, 255, 255, 0.12);
  color: #8d8571;
  font-size: 11.5px;
}
.src-seg {
  display: flex;
  gap: 6px;
  align-items: baseline;
}
.src-label {
  flex: none;
  padding: 0 5px;
  border-radius: 3px;
  background: rgba(176, 139, 62, 0.22);
  color: #e8cf96;
  font-size: 11.5px;
  line-height: 18px;
}
.src-detail {
  color: #dcd4bd;
  word-break: break-word;
}
.src-hint {
  margin-top: 2px;
  color: #8d8571;
  font-size: 11.5px;
  line-height: 1.5;
}
</style>
