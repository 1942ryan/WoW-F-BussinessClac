<script setup lang="ts">
/**
 * 物品图标（可选带文字）：优先无限官方库图标（API 返回的 icon 字段，即 /tubiao/<name>.jpg），
 * 官方图裂/缺失时回退原版 wowhead 图标 CDN（图标命名体系一致，inv_xxx / spell_xxx）。
 *
 * 传入 itemId 后启用悬停详情：**图标和文字都算悬停区**——把物品名放进默认插槽即可：
 *   <ItemIcon :icon="m.icon" :name="m.name" :item-id="m.item_id">{{ m.name }}</ItemIcon>
 * 悬停整块（图标 + 名称）停留 250ms 弹出游戏内风格物品卡（见 ItemTooltip.vue）。
 */
import { computed, ref, useSlots } from "vue";
import ItemTooltip from "./ItemTooltip.vue";

const props = withDefaults(
  defineProps<{
    icon?: string | null;
    name?: string;
    size?: number;
    /** 传入后启用悬停物品详情 tooltip */
    itemId?: number | null;
  }>(),
  { icon: null, name: "", size: 24, itemId: null }
);

const slots = useSlots();
const fallback = ref(false);
const hovering = ref(false);
const wrapEl = ref<HTMLElement | null>(null);

/** 从官方 URL 提取图标名：https://wowforever.wclbox.com/tubiao/inv_ingot_02.jpg -> inv_ingot_02 */
const iconName = computed(() => {
  const src = props.icon;
  if (!src) return null;
  const m = src.match(/([^/]+?)(?:\.[a-z]+)?$/i);
  return m ? m[1] : null;
});

const src = computed(() => {
  if (!props.icon || fallback.value) {
    // 无官方图标或官方图标加载失败 → 原版 wowhead（同命名体系）
    if (fallback.value && iconName.value) {
      return `https://wow.zamimg.com/images/wow/icons/large/${iconName.value}.jpg`;
    }
    return null;
  }
  return props.icon;
});

function onError() {
  if (!fallback.value && iconName.value) fallback.value = true;
}
</script>

<template>
  <span
    ref="wrapEl"
    class="ic-wrap"
    :class="{ 'ic-hover': itemId != null, 'ic-named': !!slots.default }"
    @mouseenter="itemId != null && (hovering = true)"
    @mouseleave="hovering = false"
  >
    <img
      v-if="src"
      class="item-icon"
      :src="src"
      :width="size"
      :height="size"
      :title="itemId == null ? (name || undefined) : undefined"
      :alt="name || ''"
      loading="lazy"
      decoding="async"
      @error="onError"
    />
    <span v-else class="item-icon item-icon-empty" :style="{ width: size + 'px', height: size + 'px' }" />
    <span v-if="slots.default" class="ic-text"><slot /></span>
    <ItemTooltip
      v-if="itemId != null"
      :item-id="itemId"
      :visible="hovering"
      :anchor="wrapEl"
      @keep="hovering = true"
      @leave="hovering = false"
    />
  </span>
</template>

<style scoped>
.ic-wrap {
  display: inline-flex;
  align-items: center;
  gap: 5px;
  flex: none;
  position: relative;
  min-width: 0;
}
/* 图标 + 文字整块都是悬停区，给个帮助光标提示「这里有详情」 */
.ic-wrap.ic-hover {
  cursor: help;
}
.ic-text {
  min-width: 0;
}
.ic-wrap.ic-hover:hover .ic-text {
  text-decoration: underline dotted rgba(176, 139, 62, 0.85);
  text-underline-offset: 3px;
}
.item-icon {
  display: inline-block;
  vertical-align: middle;
  border-radius: 3px;
  background: rgba(128, 128, 128, 0.12);
  object-fit: cover;
  flex: none;
}
.item-icon-empty {
  border: 1px dashed rgba(128, 128, 128, 0.35);
}
</style>
