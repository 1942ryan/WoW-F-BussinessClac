<template>
  <div class="dialog-mask" @click.self="$emit('close')">
    <div class="dialog panel">
      <h2>导出采购清单到 AUC</h2>
      <p class="muted" style="margin-top: 0">
        把本次路线算出的采购清单生成 AUC 关注清单文本。游戏内 AUC 关注清单导入粘贴后，
        按清单导出价格回本工具导入，即可用真实市价重算成本。
      </p>
      <div class="muted">
        清单名「{{ listName }}」共 {{ items.length }} 个物品
        （材料 {{ countOf("material") }} · 设计图 {{ countOf("design") }}）
      </div>
      <textarea :value="text" readonly rows="8" style="margin-top: 6px; font-family: monospace; font-size: 12px"></textarea>
      <div class="flex" style="margin-top: 10px">
        <button class="btn primary" @click="copyText">{{ copied ? "已复制 ✓" : "复制文本" }}</button>
        <button class="btn" @click="download">下载 .txt</button>
        <button class="btn" @click="showAll = !showAll">
          {{ showAll ? "收起图标预览" : `展开图标预览（前 ${previewLimit} 个）` }}
        </button>
      </div>
      <div v-if="showAll" class="icon-preview">
        <span v-for="it in items.slice(0, previewLimit)" :key="it.item_id" class="icon-cell" :title="it.name">
          <ItemIcon :icon="it.icon" :name="it.name" :size="28" :item-id="it.item_id" />
        </span>
        <span v-if="items.length > previewLimit" class="muted" style="align-self: center">
          ……等共 {{ items.length }} 个
        </span>
      </div>
      <div class="flex" style="margin-top: 14px">
        <button class="btn" @click="$emit('close')">关闭</button>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed, ref } from "vue";
import ItemIcon from "@/components/ItemIcon.vue";
import type { MaterialTotal } from "@/types";

const props = defineProps<{
  professionName: string;
  materials: MaterialTotal[];
}>();
defineEmits<{ close: [] }>();

const copied = ref(false);
const showAll = ref(false);
const previewLimit = 120;

const items = computed(() =>
  props.materials.map((m) => ({
    item_id: m.item_id,
    name: m.name,
    icon: m.icon ?? null,
    kind: m.kind === "design" ? "design" : "material",
  }))
);
const listName = computed(() => `${props.professionName}采购清单`);
const text = computed(() => [listName.value, ...items.value.map((i) => i.name)].join("^"));

function countOf(kind: string) {
  return items.value.filter((i) => i.kind === kind).length;
}

async function copyText() {
  try {
    await navigator.clipboard.writeText(text.value);
    copied.value = true;
    setTimeout(() => (copied.value = false), 1500);
  } catch {
    alert("浏览器不允许自动复制，请手动全选复制");
  }
}

function download() {
  const blob = new Blob([text.value], { type: "text/plain;charset=utf-8" });
  const a = document.createElement("a");
  a.href = URL.createObjectURL(blob);
  a.download = `AUC采购清单-${listName.value}.txt`;
  a.click();
  URL.revokeObjectURL(a.href);
}
</script>

<style scoped>
.dialog-mask {
  position: fixed; inset: 0; background: rgba(30, 25, 15, 0.45);
  display: flex; align-items: center; justify-content: center; z-index: 50;
}
.dialog { width: 640px; max-width: 94vw; max-height: 92vh; overflow-y: auto; }
.icon-preview {
  display: flex; flex-wrap: wrap; gap: 4px; margin-top: 8px;
  max-height: 180px; overflow-y: auto; padding: 6px;
  background: rgba(128, 128, 128, 0.08); border-radius: 6px;
}
.icon-cell { line-height: 0; }
</style>
