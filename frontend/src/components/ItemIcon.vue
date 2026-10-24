<script setup lang="ts">
/**
 * 物品图标：优先无限官方库图标（API 返回的 icon 字段，即 /tubiao/<name>.jpg）。
 * 官方图裂/缺失时回退原版 wowhead 图标 CDN（图标命名体系一致，inv_xxx / spell_xxx）。
 */
import { computed, ref } from "vue";

const props = withDefaults(
  defineProps<{
    icon?: string | null;
    name?: string;
    size?: number;
  }>(),
  { icon: null, name: "", size: 24 }
);

const fallback = ref(false);

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
  <img
    v-if="src"
    class="item-icon"
    :src="src"
    :width="size"
    :height="size"
    :title="name || undefined"
    :alt="name || ''"
    loading="lazy"
    decoding="async"
    @error="onError"
  />
  <span v-else class="item-icon item-icon-empty" :style="{ width: size + 'px', height: size + 'px' }" />
</template>

<style scoped>
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
