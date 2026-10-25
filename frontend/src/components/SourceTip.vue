<script setup lang="ts">
/**
 * 配方来源详情浮层（悬停「来源」列弹出）。
 * 内容来自后端 RecipeOut.source_detail（纯文本，\n 分行）。
 * 与 ItemTooltip 一致：Teleport 到 body + fixed 定位，避免被表格滚动容器裁剪。
 */
import { ref, watch } from "vue";

const props = withDefaults(
  defineProps<{
    text: string | null;
    visible: boolean;
    anchor: HTMLElement | null;
  }>(),
  { text: null, visible: false, anchor: null }
);

const pos = ref({ left: 0, top: 0 });

function place() {
  const el = props.anchor;
  if (!el) return;
  const r = el.getBoundingClientRect();
  const w = 340;
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
      <div
        v-for="(line, i) in text.split('\n')"
        :key="i"
        :class="i === 0 ? 'tip-title' : 'tip-row'"
      >
        {{ line }}
      </div>
    </div>
  </Teleport>
</template>

<style scoped>
.src-tip {
  position: fixed;
  z-index: 210;
  width: 340px;
  max-width: calc(100vw - 16px);
  padding: 8px 11px;
  background: rgba(18, 16, 12, 0.96);
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
</style>
