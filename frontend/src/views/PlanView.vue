<template>
  <div v-if="!session.state.serverId" class="panel">
    <div class="alert warn">请先回到首页选择服务器。</div>
    <RouterLink class="btn primary" to="/">去选择服务器</RouterLink>
  </div>

  <template v-else>
    <!-- ============ 置顶：计算参数（全宽） ============ -->
    <section class="panel">
      <h2>
        <span class="flex" style="gap: 8px; align-items: center">
          <ItemIcon :icon="profIcon" :name="profName" :size="24" :item-id="null" />
          计算参数 · {{ profName }}
        </span>
        <FactionIcon v-if="session.state.serverFaction !== 'both'"
                     :faction="session.state.serverFaction" :size="18" style="margin-left: 6px" />
      </h2>

      <div class="param-row">
        <label class="field">当前技能
          <input type="number" min="0" max="375" v-model.number="fromSkill" style="width: 70px" />
        </label>
        <label class="field">目标技能
          <input type="number" min="1" max="375" v-model.number="toSkill" style="width: 70px" />
        </label>
        <label class="field">价格口径
          <select v-model="priceMode">
            <option value="latest">最新数据</option>
            <option value="median">中位数</option>
          </select>
        </label>
        <button class="btn primary" @click="runCalc" :disabled="loading || !validRange">
          {{ loading ? "计算中…" : "计算路线" }}
        </button>
        <button class="btn" @click="showImport = true" title="导入 AUC 价格后自动重算">价格导入</button>
        <button class="btn" @click="showTemplate = true"
                title="生成 AUC 关注清单，去游戏内按清单导出价格">导出模板</button>
        <button class="btn" @click="showShopping = true" :disabled="!result || !result.materials.length"
                title="本次路线的材料采购清单（默认折叠，点击在最右展开）">
          材料采购清单<template v-if="result">（{{ result.materials.length }}）</template>
        </button>
      </div>

      <div class="param-row">
        <span class="pill">已屏蔽配方 {{ session.state.blockedRecipeIds.length }}</span>
        <span class="pill">已屏蔽物品 {{ session.state.blockedItemIds.length }}</span>
        <span class="pill">确认采用 {{ session.state.confirmedRecipeIds.length }}</span>
        <button class="btn small" @click="onClearOverrides">清空全部屏蔽/确认</button>
      </div>

      <p class="muted rules-note">
        计算规则已固定：涨点按 WoW 客户端公式（橙档 100%，黄/绿档 =(灰档−当前)/(灰档−黄档) 递减）；
        成品默认卖拍卖行，可在下方配方列表逐条改「卖店」；设计图配方自动计入，图纸按拍卖行价一次性计入成本。
      </p>

      <!-- 确认采用列表（可填次数）：次数是上限，不是强制制作量 -->
      <details v-if="confirmedList.length" class="confirm-block">
        <summary>确认采用 · 制作次数（{{ confirmedList.length }}）</summary>
        <p class="muted" style="margin: 6px 0 8px; font-size: 12px; line-height: 1.5">
          确认采用 = 当前技能下<b>优先做</b>这个配方 + <b>最多做 N 次</b>（次数是上限，不是目标）。
          长 CD 配方（如每日 1 次的转化）按一个查询周期内可做次数填，用完后自动退出路线；
          不填默认 1 次。若配方当前技能段用不到或本来就会被选中，确认与填次数都不会改变路线。
        </p>
        <table class="grid nowrap">
          <thead><tr><th>配方</th><th class="num" style="width: 76px">次数</th><th></th></tr></thead>
          <tbody>
            <tr v-for="r in confirmedList" :key="r.id">
              <td>
                <span class="flex" style="gap: 6px">
                  <ItemIcon :icon="r.product_icon" :name="r.product_name" :size="22"
                            :item-id="r.product_item_id" />
                  <span>{{ r.product_name }}</span>
                </span>
              </td>
              <td class="num">
                <input type="number" min="1" max="999" style="width: 60px"
                       :value="session.confirmedCountOf(r.id)"
                       @change="onCountChange(r.id, $event)" />
              </td>
              <td>
                <button class="btn small danger" @click="session.toggleConfirmRecipe(r.id)">移除</button>
              </td>
            </tr>
          </tbody>
        </table>
      </details>
    </section>

    <!-- ============ 主体：左 3/4 配方列表，右 1/4 计算结果 ============ -->
    <div class="plan-body">
      <!-- 左栏：配方列表 -->
      <section class="panel">
        <h2>配方列表 · 点击操作</h2>
        <div class="flex flex-wrap" style="margin-bottom: 10px">
          <input v-model="recipeQuery" type="text" placeholder="搜索成品或材料名称…" style="width: 260px" />
          <label class="field">
            <input type="checkbox" v-model="onlyUsed" /> 只看路线用到的
          </label>
          <span class="muted">共 {{ filteredRecipes.length }} 个配方参与计算</span>
        </div>
        <div class="table-scroll">
          <table class="grid nowrap">
            <thead>
              <tr>
                <th>成品</th>
                <th class="wrap">材料（单价/来源）</th>
                <th class="num">生产成本</th>
                <th>产物处置（点价格即选中）</th>
                <th>技能档</th>
                <th>来源</th>
                <th class="num">实际成本</th>
                <th>操作</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="r in visibleRecipes" :key="r.id"
                  :class="{ used: isUsed(r.id) }">
                <td>
                  <span class="flex" style="gap: 6px">
                    <ItemIcon :icon="r.product_icon" :name="r.product_name" :size="24"
                              :item-id="r.product_item_id" />
                    <span>{{ r.product_name }}</span>
                  </span>
                  <span v-if="r.product_qty > 1" class="muted"> ×{{ r.product_qty }}</span>
                  <span v-if="r.is_new" class="tag new">新</span>
                  <span v-if="r.product_kind === 'enchant'" class="tag trainer">附魔</span>
                </td>
                <td class="wrap">
                  <div v-for="m in r.materials" :key="m.item_id" class="flex" style="gap: 4px">
                    <ItemIcon :icon="m.icon" :name="m.name" :size="20" :item-id="m.item_id" />
                    <span>{{ m.name }} ×{{ m.qty }}</span>
                    <span v-if="m.unit_price !== null" class="money muted">
                      <Money :value="m.unit_price" :size="11" />
                      <span class="tag" :class="m.price_source === 'npc' ? 'npc' : 'ah'">
                        {{ m.price_source === "npc" ? "NPC" : "拍卖" }}
                      </span>
                    </span>
                    <span v-else class="neg">无价格</span>
                    <button class="btn small danger" @click="onBlockItem(m.item_id)"
                            :title="'屏蔽后，所有需要「' + m.name + '」的配方都不参与计算'">屏蔽</button>
                  </div>
                </td>
                <td class="num"><Money v-if="r.mat_cost !== null" :value="r.mat_cost" /><span v-else>—</span></td>
                <td>
                  <div class="disp-btns">
                    <button class="price-btn" :class="{ active: curDisp(r) === 'sell_npc' }"
                            @click="onDispChange(r.id, 'sell_npc')"
                            title="卖给 NPC（价 = 卖店价）">
                      <span class="pb-k">卖店</span>
                      <Money v-if="r.product_npc_price !== null" :value="r.product_npc_price" :size="12" />
                      <span v-else class="muted">—</span>
                    </button>
                    <button class="price-btn" :class="{ active: curDisp(r) === 'sell_ah' }"
                            @click="onDispChange(r.id, 'sell_ah')"
                            title="卖给拍卖行（价 = 当前有效拍卖价）">
                      <span class="pb-k">拍卖行</span>
                      <Money v-if="r.product_ah_price !== null" :value="r.product_ah_price" :size="12" />
                      <span v-else class="muted">无价</span>
                    </button>
                    <button v-if="session.recipeDispositionOf(r.id)" class="price-btn ghost"
                            @click="onDispChange(r.id, '')" title="清除本配方覆盖，回到跟随全局（卖拍卖行）">↺</button>
                  </div>
                </td>
                <td class="money">
                  {{ r.skill_orange }} / {{ r.skill_yellow }} / {{ r.skill_green }} / {{ r.skill_gray }}
                </td>
                <td>
                  <span v-if="r.source_type === 'trainer'" class="tag trainer">训练师</span>
                  <span v-else-if="r.source_type === 'design'" class="tag design">设计图</span>
                  <span v-else class="tag trainer">{{ r.source_type }}</span>
                </td>
                <td class="num">
                  <Money v-if="r.net_cost !== null" :value="r.net_cost" neg-as-earn />
                  <span v-else>—</span>
                </td>
                <td style="white-space: nowrap">
                  <button class="btn small" :class="{ active: session.state.blockedRecipeIds.includes(r.id) }"
                          @click="session.toggleBlockRecipe(r.id)">
                    {{ session.state.blockedRecipeIds.includes(r.id) ? "已屏蔽" : "屏蔽" }}
                  </button>
                  <button class="btn small" :class="{ active: session.state.confirmedRecipeIds.includes(r.id) }"
                          @click="session.toggleConfirmRecipe(r.id)"
                          title="确认采用：当前技能下优先做这个，次数是上限（默认 1 次）">
                    {{ session.state.confirmedRecipeIds.includes(r.id) ? "已确认" : "确认采用" }}
                  </button>
                  <span v-if="session.state.confirmedRecipeIds.includes(r.id)" class="flex" style="gap: 2px; display: inline-flex">
                    ×<input type="number" min="1" max="999" style="width: 52px"
                            :value="session.confirmedCountOf(r.id)"
                            @change="onCountChange(r.id, $event)"
                            title="制作次数上限（长 CD 配方按周期内可做次数填）" />
                  </span>
                </td>
              </tr>
            </tbody>
          </table>
        </div>
      </section>

      <!-- 右栏：计算结果（吸顶） -->
      <section class="panel plan-results" v-if="result">
        <h2>
          <span class="flex" style="gap: 8px; align-items: center">
            <ItemIcon :icon="profIcon" :name="result.profession.name" :size="26" :item-id="null" />
            计算结果 {{ result.params.from_skill }} → {{ result.params.to_skill }}
          </span>
        </h2>

        <div class="summary-cards">
          <div class="card"><div class="k">总制作次数</div><div class="v">{{ Math.round(result.totals.crafts) }}</div></div>
          <div class="card">
            <div class="k">花费</div>
            <div class="v"><Money :value="result.totals.net" :size="14" neg-as-earn /></div>
          </div>
        </div>

        <div v-if="result.warnings.length" class="alert warn">
          <div v-for="w in result.warnings.slice(0, 8)" :key="w">⚠ {{ w }}</div>
        </div>

        <h3>路线步骤</h3>
        <div style="overflow-x: auto">
          <table class="grid nowrap" v-if="result.steps.length">
            <thead>
              <tr>
                <th>技能区间</th><th>制作</th><th class="num">次数</th>
                <th>档位</th><th class="num">花费</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="(s, i) in result.steps" :key="i">
                <td class="money">{{ Math.round(s.skill_from) }} → {{ Math.round(s.skill_to) }}</td>
                <td>
                  <span class="flex" style="gap: 6px">
                    <ItemIcon :icon="s.product_icon" :name="s.recipe_name" :size="24"
                              :item-id="s.product_item_id" />
                    <span>{{ s.recipe_name }}</span>
                  </span>
                  <span v-if="s.confirmed" class="tag confirmed">确认采用</span>
                  <span v-if="s.disposition" class="tag disp">{{ dispLabel(s.disposition) }}</span>
                  <span v-if="s.design_cost" class="tag design" :title="'设计图：' + (s.design_name ?? '')">
                    图纸 <Money :value="s.design_cost" :size="11" />
                  </span>
                </td>
                <td class="num">{{ Math.round(s.crafts) }}</td>
                <td>
                  <span class="tag" :class="bandClass(s.band)">
                    {{ bandLabel(s.band) }} {{ probLabel(s) }}
                  </span>
                </td>
                <td class="num"><Money :value="s.net" neg-as-earn /></td>
              </tr>
            </tbody>
          </table>
          <div v-else class="empty">当前价格与筛选条件下没有可用的路线，请检查价格导入或放宽屏蔽。</div>
        </div>

        <details style="margin-top: 10px">
          <summary class="muted">未参与计算的配方（{{ result.excluded.length }}）</summary>
          <table class="grid" style="margin-top: 8px">
            <thead><tr><th>配方</th><th>原因</th></tr></thead>
            <tbody>
              <tr v-for="e in result.excluded.slice(0, 100)" :key="e.recipe_id">
                <td>{{ e.name }}</td><td class="muted">{{ e.reason }}</td>
              </tr>
            </tbody>
          </table>
        </details>

        <div class="flex" style="margin-top: 14px">
          <button class="btn primary" @click="onSave">保存 / 分享这条路线</button>
        </div>
      </section>

      <section class="panel" v-else>
        <h2>计算结果</h2>
        <div class="empty">设置好技能区间后点「计算路线」，这里显示分阶段路线与总花费。</div>
      </section>
    </div>

    <!-- ============ 材料采购清单：二级抽屉，平时折叠，点击出现在最右 ============ -->
    <div v-if="showShopping" class="drawer-mask" @click.self="showShopping = false">
      <aside class="drawer">
        <div class="flex" style="justify-content: space-between; align-items: center">
          <h2 style="margin: 0">材料采购清单</h2>
          <button class="btn small" @click="showShopping = false">✕ 关闭</button>
        </div>
        <p class="muted" style="font-size: 12px; line-height: 1.5">
          本次路线要买的全部材料（按花费排序）。可导出为 AUC 关注清单，去游戏内按清单导价回填。
        </p>
        <button class="btn primary" @click="showShoppingExport = true" v-if="result && result.materials.length">
          导出 AUC 清单
        </button>
        <div style="overflow-x: auto; margin-top: 10px">
          <table class="grid nowrap" v-if="result && result.materials.length">
            <thead>
              <tr><th>材料</th><th class="num">数量</th><th class="num">单价</th><th class="num">小计</th></tr>
            </thead>
            <tbody>
              <tr v-for="m in result!.materials" :key="m.item_id">
                <td>
                  <span class="flex" style="gap: 6px">
                    <ItemIcon :icon="m.icon" :name="m.name" :size="22" :item-id="m.item_id" />
                    <span>{{ m.name }}</span>
                  </span>
                  <span v-if="m.kind === 'design'" class="tag design">设计图</span>
                </td>
                <td class="num">{{ Math.round(m.qty) }}</td>
                <td class="num"><Money v-if="m.unit_price !== null" :value="m.unit_price" /><span v-else>—</span></td>
                <td class="num"><Money v-if="m.cost !== null" :value="m.cost" /><span v-else>—</span></td>
              </tr>
            </tbody>
          </table>
          <div v-else class="empty">暂无材料数据，请先计算路线。</div>
        </div>
      </aside>
    </div>

    <div v-if="showSave" class="save-mask" @click.self="showSave = false">
      <div class="save-dialog panel">
        <h2>保存路线</h2>
        <label class="field">路线标题
          <input v-model="saveTitle" type="text" style="width: 280px"
                 :placeholder="profName + ' ' + fromSkill + '→' + toSkill" />
        </label>
        <div style="margin-top: 8px">
          <label class="field">作者昵称
            <input v-model="saveAuthor" type="text" style="width: 160px" placeholder="可选" />
          </label>
        </div>
        <div style="margin-top: 8px">
          <label class="field">备注
            <input v-model="saveNotes" type="text" style="width: 320px" placeholder="可选，如：避开 Bronze 短缺" />
          </label>
        </div>
        <div style="margin-top: 8px">
          <label class="field"><input type="checkbox" v-model="savePublic" /> 公开分享（同服玩家可见）</label>
        </div>
        <div class="flex" style="margin-top: 14px">
          <button class="btn primary" @click="onConfirmSave" :disabled="!saveTitle.trim()">保存</button>
          <button class="btn" @click="showSave = false">取消</button>
        </div>
      </div>
    </div>

    <PriceImportDialog v-if="showImport" :server-id="session.state.serverId!"
                       @close="showImport = false" @imported="onImported" />
    <TemplateExportDialog v-if="showTemplate" :profession-key="session.state.professionKey"
                          @close="showTemplate = false" />
    <ShoppingExportDialog v-if="showShoppingExport && result"
                          :profession-name="result.profession.name"
                          :materials="result.materials"
                          @close="showShoppingExport = false" />
  </template>
</template>

<script setup lang="ts">
import { computed, onMounted, ref } from "vue";
import { RouterLink } from "vue-router";
import { api } from "@/api/client";
import FactionIcon from "@/components/FactionIcon.vue";
import ItemIcon from "@/components/ItemIcon.vue";
import Money from "@/components/Money.vue";
import PriceImportDialog from "@/components/PriceImportDialog.vue";
import ShoppingExportDialog from "@/components/ShoppingExportDialog.vue";
import TemplateExportDialog from "@/components/TemplateExportDialog.vue";
import { useSessionStore } from "@/stores/session";
import type { CalcResult, Disposition, Profession, Recipe } from "@/types";

const session = useSessionStore();
const professions = ref<Profession[]>([]);
const recipes = ref<Recipe[]>([]);
const result = ref<CalcResult | null>(null);
const loading = ref(false);
const recipeQuery = ref("");
const onlyUsed = ref(false);

const fromSkill = ref(session.state.fromSkill);
const toSkill = ref(session.state.toSkill);
const priceMode = ref(session.state.priceMode);

const showSave = ref(false);
const showImport = ref(false);
const showTemplate = ref(false);
const showShopping = ref(false);
const showShoppingExport = ref(false);
const saveTitle = ref("");
const saveAuthor = ref("");
const saveNotes = ref("");
const savePublic = ref(true);

const profName = computed(() => professions.value.find((p) => p.key === session.state.professionKey)?.name ?? "");
const profIcon = computed(() => professions.value.find((p) => p.key === session.state.professionKey)?.icon ?? null);
const validRange = computed(() => toSkill.value > fromSkill.value);
const filteredRecipes = computed(() => {
  const q = recipeQuery.value.trim();
  let list = recipes.value;
  if (onlyUsed.value && result.value) {
    const usedIds = new Set(result.value.steps.map((s) => s.recipe_id));
    list = list.filter((r) => usedIds.has(r.id));
  }
  if (!q) return list;
  return list.filter(
    (r) => r.product_name.includes(q) || r.materials.some((m) => m.name.includes(q))
  );
});
const visibleRecipes = computed(() => filteredRecipes.value.slice(0, 400));
const confirmedList = computed(() =>
  recipes.value.filter((r) => session.state.confirmedRecipeIds.includes(r.id))
);

onMounted(async () => {
  professions.value = await api.listProfessions();
  if (session.state.serverId && session.state.professionKey) {
    await loadRecipes();
  }
});

async function loadRecipes() {
  if (!session.state.serverId || !session.state.professionKey) return;
  recipes.value = await api.listRecipes(
    session.state.professionKey,
    session.state.serverId,
    priceMode.value,
    "sell_ah",
    session.state.recipeDispositions
  );
}

function isUsed(id: number) {
  return result.value?.steps.some((s) => s.recipe_id === id) ?? false;
}

function bandLabel(b: string) {
  return b === "orange" ? "橙" : b === "yellow" ? "黄" : "绿";
}
function bandClass(b: string) {
  return b === "orange" ? "band-o" : b === "yellow" ? "band-y" : "band-g";
}

/** 档位几率展示：合并段内几率衰减，显示 100%→20%。 */
function probLabel(s: CalcResult["steps"][number]) {
  const a = Math.round(s.prob * 100);
  if (s.prob_end != null && Math.abs(s.prob_end - s.prob) > 0.005) {
    return `${a}% → ${Math.round(s.prob_end * 100)}%`;
  }
  return `${a}%`;
}

function dispLabel(d: string) {
  return d === "sell_ah" ? "→拍卖" : d === "sell_npc" ? "→卖店" : "→自用";
}

/** 当前生效处置：单配方覆盖优先，否则跟随全局（全局固定为卖拍卖行）。 */
function curDisp(r: Recipe): Disposition {
  return (session.recipeDispositionOf(r.id) as Disposition) || "sell_ah";
}

function onDispChange(id: number, d: Disposition | "") {
  session.setRecipeDisposition(id, d);
  loadRecipes();
}

function onCountChange(id: number, e: Event) {
  const v = Number((e.target as HTMLInputElement).value);
  session.setConfirmedCount(id, Number.isFinite(v) ? v : 1);
}

function onBlockItem(itemId: number) {
  session.toggleBlockItem(itemId);
}

function onClearOverrides() {
  session.clearOverrides();
}

async function runCalc() {
  if (!validRange.value) return;
  session.setRange(fromSkill.value, toSkill.value);
  session.setPriceMode(priceMode.value);
  await loadRecipes();
  loading.value = true;
  try {
    result.value = await api.calc(session.toCalcParams());
  } finally {
    loading.value = false;
  }
}

/** 价格导入完成后：刷新配方价格，已有计算结果时自动重算。 */
async function onImported() {
  showImport.value = false;
  await loadRecipes();
  if (result.value && validRange.value) {
    loading.value = true;
    try {
      result.value = await api.calc(session.toCalcParams());
    } finally {
      loading.value = false;
    }
  }
}

function onSave() {
  saveTitle.value = `${profName.value} ${fromSkill.value}→${toSkill.value}`;
  showSave.value = true;
}

async function onConfirmSave() {
  if (!saveTitle.value.trim()) return;
  const detail = await api.saveRoute({
    ...session.toCalcParams(),
    title: saveTitle.value.trim(),
    author: saveAuthor.value.trim() || undefined,
    notes: saveNotes.value.trim() || undefined,
    is_public: savePublic.value,
  });
  showSave.value = false;
  alert(`已保存！分享码：${detail.share_code}`);
}
</script>

<style scoped>
.save-mask {
  position: fixed; inset: 0; background: rgba(30, 25, 15, 0.45);
  display: flex; align-items: center; justify-content: center; z-index: 50;
}
.save-dialog { width: 480px; max-width: 92vw; }
.table-scroll {
  max-height: 560px;
  overflow: auto;
  border-radius: 6px;
}
.table-scroll thead th {
  position: sticky;
  top: 0;
  z-index: 2;
  background: var(--panel-bg, #f7f4ec);
}
.param-row {
  display: flex;
  flex-wrap: wrap;
  gap: 12px;
  align-items: center;
}
.param-row + .param-row { margin-top: 10px; }
.rules-note {
  margin: 10px 0 0;
  font-size: 12px;
  line-height: 1.6;
}
.confirm-block {
  margin-top: 10px;
  border: 1px solid var(--border, #d8d3c4);
  border-radius: 6px;
  padding: 8px 12px;
}
.confirm-block summary {
  cursor: pointer;
  font-weight: 600;
  font-size: 13px;
}
.disp-btns {
  display: flex;
  flex-wrap: wrap;
  gap: 4px;
}
.price-btn {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  padding: 3px 8px;
  border: 1px solid var(--border, #d8d3c4);
  border-radius: 5px;
  background: transparent;
  cursor: pointer;
  font-size: 12px;
  line-height: 1.4;
}
.price-btn:hover {
  border-color: #b08b3e;
}
.price-btn.active {
  border-color: #b08b3e;
  background: rgba(176, 139, 62, 0.16);
  font-weight: 600;
}
.price-btn.ghost {
  padding: 3px 6px;
  color: var(--muted);
}
.pb-k {
  color: var(--muted);
  font-size: 11px;
}
.price-btn.active .pb-k {
  color: inherit;
}
</style>
