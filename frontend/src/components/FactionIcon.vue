<script setup lang="ts">
/** 阵营图标：联盟蓝狮旗 / 部落红龙旗（无限官方图标库）。 */
import { computed } from "vue";
import type { Faction } from "@/types";

const props = withDefaults(
  defineProps<{ faction?: Faction | string | null; size?: number }>(),
  { faction: "both", size: 20 }
);

const CDN = "https://wowforever.wclbox.com/tubiao";
const ICONS: Record<string, string> = {
  alliance: `${CDN}/inv_bannerpvp_02.jpg`, // 蓝底金狮
  horde: `${CDN}/inv_bannerpvp_01.jpg`, // 红底黑龙
  both: `${CDN}/inv_misc_coin_02.jpg`, // 双阵营共用（无阵营徽记时用中性图标）
};

const src = computed(() => ICONS[props.faction ?? "both"] ?? ICONS.both);
const label = computed(() =>
  props.faction === "alliance" ? "联盟" : props.faction === "horde" ? "部落" : "双阵营"
);
</script>

<template>
  <img
    class="faction-icon"
    :src="src"
    :width="size"
    :height="size"
    :title="label"
    :alt="label"
    loading="lazy"
    decoding="async"
  />
</template>

<style scoped>
.faction-icon {
  display: inline-block;
  vertical-align: middle;
  border-radius: 3px;
  flex: none;
}
</style>
