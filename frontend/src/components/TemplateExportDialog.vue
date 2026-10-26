<template>
  <div class="dialog-mask" @click.self="$emit('close')">
    <div class="dialog panel">
      <h2>导出 AUC 关注清单模板</h2>
      <p class="muted" style="margin-top: 0">
        按专业生成该专业冲级所需的全部物品（材料 / 成品 / 设计图）。
        在游戏内 AUC 的关注清单导入里粘贴下面的文本，再按清单导出价格，回到本工具导入即可。
        <RouterLink to="/guide" @click="$emit('close')">不知道怎么做？看图文教程 →</RouterLink>
      </p>

      <div class="flex flex-wrap" style="gap: 12px; align-items: flex-end">
        <label class="field">专业
          <select v-model="profKey" @change="load">
            <option v-for="p in professions" :key="p.key" :value="p.key">{{ p.name }}</option>
          </select>
        </label>
        <label class="field">技能范围（可选）
          <input type="number" v-model.number="fromSkill" min="0" style="width: 64px" placeholder="起" />
          —
          <input type="number" v-model.number="toSkill" min="1" style="width: 64px" placeholder="止" />
        </label>
        <button class="btn" @click="load" :disabled="loading">{{ loading ? "生成中…" : "重新生成" }}</button>
      </div>

      <div v-if="watch" style="margin-top: 12px">
        <div class="muted">
          清单名「{{ watch.list_name }}」共 {{ watch.count }} 个物品
          （材料 {{ countOf("material") }} · 成品 {{ countOf("product") }} · 设计图 {{ countOf("design") }}）
        </div>
        <textarea :value="watch.text" readonly rows="8" style="margin-top: 6px; font-family: monospace; font-size: 12px"></textarea>
        <div class="flex" style="margin-top: 10px">
          <button class="btn primary" @click="copyText">{{ copied ? "已复制 ✓" : "复制文本" }}</button>
          <button class="btn" @click="download">下载 .txt</button>
          <button class="btn" @click="showAll = !showAll">
            {{ showAll ? "收起图标预览" : `展开图标预览（前 ${previewLimit} 个）` }}
          </button>
        </div>
        <div v-if="showAll" class="icon-preview">
        <span v-for="it in watch.items.slice(0, previewLimit)" :key="it.item_id" class="icon-cell" :title="it.name">
            <ItemIcon :icon="it.icon" :name="it.name" :size="28" :item-id="it.item_id" />
        </span>
          <span v-if="watch.items.length > previewLimit" class="muted" style="align-self: center">
            ……等共 {{ watch.items.length }} 个
          </span>
        </div>
      </div>
      <div v-else-if="error" class="alert warn" style="margin-top: 12px">{{ error }}</div>

      <div class="flex" style="margin-top: 14px">
        <button class="btn" @click="$emit('close')">关闭</button>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { onMounted, ref } from "vue";
import { RouterLink } from "vue-router";
import { api } from "@/api/client";
import ItemIcon from "@/components/ItemIcon.vue";
import type { Profession, Watchlist } from "@/types";

const props = defineProps<{ professionKey?: string }>();
const emit = defineEmits<{ close: [] }>();

const professions = ref<Profession[]>([]);
const profKey = ref(props.professionKey ?? "");
const fromSkill = ref<number | undefined>(undefined);
const toSkill = ref<number | undefined>(undefined);
const watch = ref<Watchlist | null>(null);
const loading = ref(false);
const error = ref("");
const copied = ref(false);
const showAll = ref(false);
const previewLimit = 120;

function countOf(kind: string) {
  return watch.value?.items.filter((i) => i.kind === kind).length ?? 0;
}

async function load() {
  if (!profKey.value) return;
  loading.value = true;
  error.value = "";
  try {
    watch.value = await api.watchlist(profKey.value, fromSkill.value, toSkill.value);
  } catch (e: unknown) {
    const msg = (e as { response?: { data?: { detail?: string } } })?.response?.data?.detail;
    error.value = `生成失败：${msg ?? String(e)}`;
    watch.value = null;
  } finally {
    loading.value = false;
  }
}

async function copyText() {
  if (!watch.value) return;
  try {
    await navigator.clipboard.writeText(watch.value.text);
    copied.value = true;
    setTimeout(() => (copied.value = false), 1500);
  } catch {
    // 剪贴板不可用时退回选中提示
    alert("浏览器不允许自动复制，请手动全选复制");
  }
}

function download() {
  if (!watch.value) return;
  const blob = new Blob([watch.value.text], { type: "text/plain;charset=utf-8" });
  const a = document.createElement("a");
  a.href = URL.createObjectURL(blob);
  a.download = `AUC关注清单-${watch.value.list_name}.txt`;
  a.click();
  URL.revokeObjectURL(a.href);
}

onMounted(async () => {
  professions.value = await api.listProfessions();
  if (!profKey.value && professions.value.length) {
    profKey.value = professions.value[0].key;
  }
  await load();
});
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
