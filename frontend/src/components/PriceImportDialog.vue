<template>
  <div class="dialog-mask" @click.self="$emit('close')">
    <div class="dialog panel">
      <h2>导入拍卖行价格</h2>
      <p class="muted" style="margin-top: 0">
        支持游戏内 AUC 导出的价格文本，也支持文档 CSV / 物品链接格式。导入后自动刷新并重算路线。
      </p>

      <div class="flex flex-wrap" style="align-items: flex-start; gap: 14px">
        <div class="grow">
          <textarea v-model="csvText" placeholder='在此粘贴 AUC 导出内容，例如：
"价格","名称","物品等级","拥有？","可售数量"
115,"劣质火药",5,"",1169
200,"劣质炸药",20,"",61'></textarea>
        </div>
        <div style="min-width: 190px">
          <div>或选择文件：</div>
          <input type="file" accept=".csv,text/csv,.txt" @change="onFile" />
          <div style="margin-top: 10px">
            <label class="field">你的昵称
              <input v-model="importedBy" type="text" style="width: 130px" placeholder="可选" />
            </label>
          </div>
          <button class="btn primary" style="margin-top: 10px" @click="onImport"
                  :disabled="importing || (!csvText.trim() && !file)">
            {{ importing ? "导入中…" : "开始导入" }}
          </button>
        </div>
      </div>

      <details style="margin-top: 10px">
        <summary class="muted">支持的格式说明</summary>
        <ul class="muted" style="font-size: 13px; line-height: 1.7">
          <li><b>AUC 拍卖行导出</b>（推荐）：表头 <code>"价格","名称","物品等级","拥有？","可售数量"</code>，
            价格为铜；「物品等级」用于区分同名不同物品（如劣质炸药 10级/20级）。</li>
          <li><b>文档 CSV</b>：表头含「名称」「单价」两列，价格支持 <code>25</code>、<code>1银20铜</code>、<code>1.5g</code>。</li>
          <li><b>物品链接格式</b>：<code>|cff...|Hitem:2840:...|h[铜锭]|h|r,25</code>，按物品 ID 精确匹配。</li>
          <li>不知道该导哪些物品？用「导出模板」生成 AUC 关注清单，在游戏内导入后按清单导出。</li>
        </ul>
      </details>

      <div v-if="summary" class="alert info" style="margin-top: 12px">
        本次导入：{{ summary.row_count }} 行 · 匹配 {{ summary.matched }} · 未匹配 {{ summary.unmatched }} · 入库 {{ summary.inserted }}
        <div v-if="summary.unmatched_names.length" class="muted" style="margin-top: 4px">
          未匹配名称（可能无限版不存在或改名）：{{ summary.unmatched_names.join("、") }}
        </div>
      </div>
      <div v-if="error" class="alert warn" style="margin-top: 12px">{{ error }}</div>

      <div class="flex" style="margin-top: 14px">
        <button class="btn" @click="$emit('close')">关闭</button>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed, ref } from "vue";
import { api } from "@/api/client";
import type { ImportSummary } from "@/types";

const props = defineProps<{ serverId: number }>();
const emit = defineEmits<{ close: []; imported: [] }>();

const serverId = computed(() => props.serverId);
const csvText = ref("");
const file = ref<File | null>(null);
const importedBy = ref("");
const importing = ref(false);
const summary = ref<ImportSummary | null>(null);
const error = ref("");

function onFile(e: Event) {
  const input = e.target as HTMLInputElement;
  file.value = input.files?.[0] ?? null;
}

async function onImport() {
  importing.value = true;
  error.value = "";
  try {
    if (file.value) {
      summary.value = await api.importPrices(file.value, serverId.value, importedBy.value);
    } else {
      summary.value = await api.importPricesText(csvText.value, serverId.value, importedBy.value);
    }
    csvText.value = "";
    file.value = null;
    emit("imported");
  } catch (e: unknown) {
    const msg = (e as { response?: { data?: { detail?: string } } })?.response?.data?.detail;
    error.value = `导入失败：${msg ?? String(e)}`;
  } finally {
    importing.value = false;
  }
}
</script>

<style scoped>
.dialog-mask {
  position: fixed; inset: 0; background: rgba(30, 25, 15, 0.45);
  display: flex; align-items: center; justify-content: center; z-index: 50;
}
.dialog { width: 640px; max-width: 94vw; max-height: 92vh; overflow-y: auto; }
</style>
