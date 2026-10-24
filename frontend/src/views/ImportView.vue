<template>
  <div v-if="!session.state.serverId" class="panel">
    <div class="alert warn">请先回到首页选择服务器。</div>
    <RouterLink class="btn primary" to="/">去选择服务器</RouterLink>
  </div>

  <template v-else>
    <section class="panel">
      <h2>导入拍卖行价格 · {{ session.state.serverName }}</h2>
      <p class="muted" style="margin-top: 0">
        从游戏内 AUC 插件导出 CSV 后上传；每次导入都会留存记录，同服务器玩家之后计算时自动使用这些价格。
      </p>
      <div class="flex flex-wrap" style="align-items: flex-start; gap: 14px">
        <div class="grow">
          <textarea v-model="csvText" placeholder='在此粘贴 AUC 导出内容，例如：
"价格","名称","物品等级","拥有？","可售数量"
115,"劣质火药",5,"",1169
200,"劣质炸药",20,"",61'></textarea>
        </div>
        <div style="min-width: 200px">
          <div>或选择文件：</div>
          <input type="file" accept=".csv,text/csv,.txt" @change="onFile" />
          <div style="margin-top: 10px">
            <label class="field">你的昵称
              <input v-model="importedBy" type="text" style="width: 130px" placeholder="可选" />
            </label>
          </div>
          <button class="btn primary" style="margin-top: 10px" @click="onImport"
                  :disabled="importing || (!csvText.trim() && !file)">
            开始导入
          </button>
          <button class="btn" style="margin-top: 10px" @click="showTemplate = true">
            导出模板（AUC 关注清单）
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
          <li>不知道该导哪些物品？点「导出模板」按专业生成 AUC 关注清单，在游戏内 AUC 导入该清单后按清单导出价格。</li>
        </ul>
      </details>

      <div v-if="summary" class="alert info" style="margin-top: 12px">
        本次导入：{{ summary.row_count }} 行 · 匹配 {{ summary.matched }} · 未匹配 {{ summary.unmatched }} · 入库 {{ summary.inserted }}
        <div v-if="summary.unmatched_names.length" class="muted" style="margin-top: 4px">
          未匹配名称（可能无限版不存在或改名）：{{ summary.unmatched_names.join("、") }}
        </div>
      </div>
    </section>

    <section class="panel">
      <h2>当前有效价格（{{ priceMode === "latest" ? "最新数据" : "中位数" }}）</h2>
      <div class="flex flex-wrap" style="margin-bottom: 10px">
        <select v-model="priceMode">
          <option value="latest">最新数据</option>
          <option value="median">中位数</option>
        </select>
        <input v-model="priceQuery" type="text" placeholder="搜索物品…" style="width: 200px" />
        <button class="btn" @click="loadPrices">刷新</button>
      </div>
      <table class="grid" v-if="prices.length">
        <thead>
          <tr><th>物品</th><th class="num">单价</th><th class="num">记录数</th><th>最近导入</th></tr>
        </thead>
        <tbody>
          <tr v-for="p in prices" :key="p.item_id">
            <td>{{ p.name }}</td>
            <td class="num money">{{ fmt(p.price) }}</td>
            <td class="num">{{ p.record_count }}</td>
            <td class="muted">{{ p.last_at ? new Date(p.last_at).toLocaleString("zh-CN") : "—" }}</td>
          </tr>
        </tbody>
      </table>
      <div v-else class="empty">还没有价格数据，先导入一份 AUC 导出。</div>
    </section>

    <section class="panel">
      <h2>手动录入 / 查询单个物品</h2>
      <div class="flex flex-wrap">
        <input v-model="itemQuery" type="text" placeholder="物品名称，如：秘银锭" style="width: 220px"
               @keyup.enter="onSearchItem" />
        <button class="btn" @click="onSearchItem" :disabled="!itemQuery.trim()">查询</button>
      </div>
      <div v-if="searched" style="margin-top: 10px">
        <div class="flex flex-wrap">
          <span><b>{{ searched.name }}</b>（ID {{ searched.item_id }}）</span>
          <span class="muted">NPC 卖店价 {{ fmt(searched.vendor_price) }}</span>
          <span v-if="searched.effective_ah !== null" class="money">
            当前拍卖有效价 {{ fmt(searched.effective_ah) }}
          </span>
          <span v-else class="muted">暂无拍卖价格记录</span>
          <div class="flex">
            <input v-model.number="manualPrice" type="number" min="0" placeholder="手动录价（铜）" style="width: 130px" />
            <button class="btn small" @click="onManualPrice" :disabled="manualPrice === null || manualPrice < 0">录入</button>
          </div>
        </div>
        <table class="grid" v-if="searched.history.length" style="margin-top: 8px">
          <thead><tr><th>批次</th><th class="num">单价</th><th>导入人</th><th>时间</th></tr></thead>
          <tbody>
            <tr v-for="(h, i) in searched.history" :key="i">
              <td>#{{ h.batch_id }}</td>
              <td class="num money">{{ fmt(h.unit_price) }}</td>
              <td>{{ h.imported_by ?? "—" }}</td>
              <td class="muted">{{ h.created_at ? new Date(h.created_at).toLocaleString("zh-CN") : "—" }}</td>
            </tr>
          </tbody>
        </table>
      </div>
    </section>

    <section class="panel">
      <h2>导入历史</h2>
      <table class="grid" v-if="batches.length">
        <thead>
          <tr><th>#</th><th>文件</th><th>来源</th><th class="num">匹配/未匹配</th><th>导入人</th><th>时间</th></tr>
        </thead>
        <tbody>
          <tr v-for="b in batches" :key="b.id">
            <td>{{ b.id }}</td>
            <td>{{ b.filename ?? "手动录入" }}</td>
            <td>{{ b.source === "auc" ? "AUC 导入" : "手动" }}</td>
            <td class="num">{{ b.matched }} / {{ b.unmatched }}</td>
            <td>{{ b.imported_by ?? "—" }}</td>
            <td class="muted">{{ b.created_at ? new Date(b.created_at).toLocaleString("zh-CN") : "—" }}</td>
          </tr>
        </tbody>
      </table>
      <div v-else class="empty">暂无导入记录。</div>
    </section>

    <TemplateExportDialog v-if="showTemplate" :profession-key="session.state.professionKey"
                          @close="showTemplate = false" />
  </template>
</template>

<script setup lang="ts">
import { onMounted, ref } from "vue";
import { RouterLink } from "vue-router";
import { api } from "@/api/client";
import TemplateExportDialog from "@/components/TemplateExportDialog.vue";
import { useSessionStore } from "@/stores/session";
import type { BatchInfo, EffectivePrice, ImportSummary, ItemPrice } from "@/types";

const session = useSessionStore();
const csvText = ref("");
const file = ref<File | null>(null);
const importedBy = ref("");
const importing = ref(false);
const summary = ref<ImportSummary | null>(null);
const showTemplate = ref(false);
const prices = ref<EffectivePrice[]>([]);
const priceMode = ref(session.state.priceMode);
const priceQuery = ref("");
const batches = ref<BatchInfo[]>([]);
const itemQuery = ref("");
const searched = ref<ItemPrice | null>(null);
const manualPrice = ref<number | null>(null);

onMounted(() => {
  if (session.state.serverId) {
    loadPrices();
    loadBatches();
  }
});

function fmt(copper: number | null | undefined) {
  if (copper === null || copper === undefined) return "—";
  const neg = copper < 0;
  const c = Math.abs(Math.round(copper));
  const g = Math.floor(c / 10000);
  const s = Math.floor((c % 10000) / 100);
  const k = c % 100;
  const parts: string[] = [];
  if (g) parts.push(`${g}金`);
  if (s) parts.push(`${s}银`);
  if (k || !parts.length) parts.push(`${k}铜`);
  return (neg ? "-" : "") + parts.join("");
}

function onFile(e: Event) {
  const input = e.target as HTMLInputElement;
  file.value = input.files?.[0] ?? null;
}

async function onImport() {
  if (!session.state.serverId) return;
  importing.value = true;
  try {
    if (file.value) {
      summary.value = await api.importPrices(file.value, session.state.serverId, importedBy.value);
    } else if (csvText.value.trim()) {
      summary.value = await api.importPricesText(csvText.value, session.state.serverId, importedBy.value);
    }
    csvText.value = "";
    file.value = null;
    await Promise.all([loadPrices(), loadBatches()]);
  } catch (e: unknown) {
    const msg = (e as { response?: { data?: { detail?: string } } })?.response?.data?.detail;
    alert(`导入失败：${msg ?? String(e)}`);
  } finally {
    importing.value = false;
  }
}

async function loadPrices() {
  if (!session.state.serverId) return;
  prices.value = await api.effectivePrices(session.state.serverId, priceMode.value, priceQuery.value || undefined);
}

async function loadBatches() {
  if (!session.state.serverId) return;
  batches.value = await api.listBatches(session.state.serverId);
}

async function onSearchItem() {
  const q = itemQuery.value.trim();
  if (!q) return;
  const hits = await api.searchItems(q);
  if (!hits.length) {
    searched.value = null;
    alert("未找到该物品");
    return;
  }
  searched.value = await api.itemPrice(hits[0].item_id, session.state.serverId!);
  manualPrice.value = null;
}

async function onManualPrice() {
  if (!searched.value || manualPrice.value === null || !session.state.serverId) return;
  await api.manualPrice(
    session.state.serverId,
    searched.value.item_id,
    manualPrice.value,
    importedBy.value.trim() || undefined
  );
  manualPrice.value = null;
  searched.value = await api.itemPrice(searched.value.item_id, session.state.serverId);
  await Promise.all([loadPrices(), loadBatches()]);
}
</script>
