<template>
  <div v-if="!session.state.serverId" class="panel">
    <div class="alert warn">请先回到首页选择服务器。</div>
    <RouterLink class="btn primary" to="/">去选择服务器</RouterLink>
  </div>

  <template v-else>
    <div class="plan-layout">
      <!-- ============ 左栏：计算参数 ============ -->
      <div class="plan-side">
        <section class="panel">
          <h2>计算参数 · {{ profName }}</h2>
          <div class="flex flex-wrap" style="gap: 12px">
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
          </div>

          <div class="flex flex-wrap" style="gap: 12px; margin-top: 10px">
            <label class="field">涨点几率
              <select v-model="probMode">
                <option value="formula">客户端公式（推荐）</option>
                <option value="fixed">固定档位</option>
              </select>
            </label>
            <template v-if="probMode === 'fixed'">
              <label class="field">橙
                <input type="number" min="0" max="100" v-model.number="probOrange" style="width: 56px" />%
              </label>
              <label class="field">黄
                <input type="number" min="0" max="100" v-model.number="probYellow" style="width: 56px" />%
              </label>
              <label class="field">绿
                <input type="number" min="0" max="100" v-model.number="probGreen" style="width: 56px" />%
              </label>
            </template>
          </div>
          <p v-if="probMode === 'formula'" class="muted" style="margin: 6px 0 0; font-size: 12px; line-height: 1.5">
            按 WoW 客户端实际公式：橙档 100%；黄/绿档几率 =(灰档−当前技能)/(灰档−黄档)，
            即刚变黄仍接近必涨、变绿时约 50%、向灰档递减。感觉不符可切「固定档位」按经验自填。
          </p>

          <div class="flex flex-wrap" style="gap: 12px; margin-top: 10px">
            <label class="field">成品处置（默认）
              <select v-model="disposition">
                <option value="sell_ah">卖给拍卖行</option>
                <option value="sell_npc">卖给 NPC</option>
                <option value="self_use">自用（不计收入）</option>
              </select>
            </label>
            <label class="field">
              <input type="checkbox" v-model="includeDesigns" /> 含设计图配方
            </label>
            <label v-if="includeDesigns" class="field">图纸成本
              <select v-model="designCost">
                <option value="ah">AH 购买计入</option>
                <option value="drop">掉落不计</option>
              </select>
            </label>
          </div>

          <div class="flex flex-wrap" style="margin-top: 12px">
            <button class="btn primary" @click="runCalc" :disabled="loading || !validRange">
              {{ loading ? "计算中…" : "计算路线" }}
            </button>
            <button class="btn" @click="showImport = true" title="导入 AUC 价格后自动重算">价格导入</button>
            <button class="btn" @click="showTemplate = true"
                    title="生成 AUC 关注清单，去游戏内按清单导出价格">导出模板</button>
          </div>
          <div class="flex flex-wrap" style="margin-top: 10px">
            <span class="pill">已屏蔽配方 {{ session.state.blockedRecipeIds.length }}</span>
            <span class="pill">已屏蔽物品 {{ session.state.blockedItemIds.length }}</span>
            <span class="pill">确认采用 {{ session.state.confirmedRecipeIds.length }}</span>
            <button class="btn small" @click="onClearOverrides">清空全部屏蔽/确认</button>
          </div>
        </section>

        <!-- 确认采用列表（可填次数，应对长 CD 配方） -->
        <section class="panel" v-if="confirmedList.length">
          <h2>确认采用 · 制作次数</h2>
          <p class="muted" style="margin: 0 0 8px; font-size: 12px; line-height: 1.5">
            确认采用的配方会优先制作。长 CD 配方（如每日 1 次的转化）请在右侧填次数，
            用完后自动退出路线；缺省按 1 次计。
          </p>
          <table class="grid">
            <thead><tr><th>配方</th><th class="num" style="width: 76px">次数</th><th></th></tr></thead>
            <tbody>
              <tr v-for="r in confirmedList" :key="r.id">
                <td>
                  <span class="flex" style="gap: 6px">
                    <ItemIcon :icon="r.product_icon" :name="r.product_name" :size="22" />
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
        </section>
      </div>

      <!-- ============ 右栏：结果优先 ============ -->
      <div class="plan-main">
        <section class="panel" v-if="result">
          <h2>
            <span class="flex" style="gap: 8px">
              <ItemIcon :icon="profIcon" :name="result.profession.name" :size="26" />
              计算结果 · {{ result.profession.name }} {{ result.params.from_skill }} → {{ result.params.to_skill }}
            </span>
          </h2>

          <div class="summary-cards">
            <div class="card"><div class="k">总制作次数</div><div class="v">{{ Math.round(result.totals.crafts) }}</div></div>
            <div class="card"><div class="k">材料花费</div><div class="v"><Money :value="result.totals.mat_cost" :size="14" /></div></div>
            <div class="card"><div class="k">成品收入</div><div class="v pos"><Money :value="result.totals.revenue" :size="14" /></div></div>
            <div class="card"><div class="k">净成本</div><div class="v" :class="result.totals.net < 0 ? 'pos' : 'neg'">
              <Money :value="result.totals.net" :size="14" />
            </div></div>
          </div>

          <div v-if="result.warnings.length" class="alert warn">
            <div v-for="w in result.warnings.slice(0, 8)" :key="w">⚠ {{ w }}</div>
          </div>

          <h3>路线步骤</h3>
          <table class="grid" v-if="result.steps.length">
            <thead>
              <tr>
                <th>技能区间</th><th>制作</th><th class="num">次数</th>
                <th>档位</th><th class="num">材料费</th><th class="num">收入</th><th class="num">净成本</th>
                <th class="num">图纸成本</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="(s, i) in result.steps" :key="i">
                <td class="money">{{ Math.round(s.skill_from) }} → {{ Math.round(s.skill_to) }}</td>
                <td>
                  <span class="flex" style="gap: 6px">
                    <ItemIcon :icon="s.product_icon" :name="s.recipe_name" :size="24" />
                    <span>{{ s.recipe_name }}</span>
                  </span>
                  <span v-if="s.confirmed" class="tag confirmed">确认采用</span>
                  <span v-if="s.disposition" class="tag disp">{{ dispLabel(s.disposition) }}</span>
                </td>
                <td class="num">{{ Math.round(s.crafts) }}</td>
                <td>
                  <span class="tag" :class="bandClass(s.band)">
                    {{ bandLabel(s.band) }} {{ probLabel(s) }}
                  </span>
                </td>
                <td class="num"><Money :value="s.mat_cost" /></td>
                <td class="num"><Money :value="s.revenue" /></td>
                <td class="num" :class="s.net < 0 ? 'pos' : ''"><Money :value="s.net" /></td>
                <td class="num">
                  <span v-if="s.design_cost" :title="s.design_name ?? ''"><Money :value="s.design_cost" /></span>
                  <span v-else class="muted">—</span>
                </td>
              </tr>
            </tbody>
          </table>
          <div v-else class="empty">当前价格与筛选条件下没有可用的路线，请检查价格导入或放宽屏蔽。</div>

          <h3>材料采购清单</h3>
          <table class="grid" v-if="result.materials.length">
            <thead>
              <tr><th>材料</th><th class="num">数量</th><th class="num">单价</th><th>来源</th><th class="num">小计</th></tr>
            </thead>
            <tbody>
              <tr v-for="m in result.materials" :key="m.item_id">
                <td>
                  <span class="flex" style="gap: 6px">
                    <ItemIcon :icon="m.icon" :name="m.name" :size="22" />
                    <span>{{ m.name }}</span>
                  </span>
                  <span v-if="m.kind === 'design'" class="tag design">设计图</span>
                  <span v-else-if="m.npc_limited" class="tag limited"
                        title="NPC 限量供应（如草药），冲级不能依靠，已按拍卖行计价">NPC限量</span>
                </td>
                <td class="num">{{ Math.round(m.qty) }}</td>
                <td class="num"><Money v-if="m.unit_price !== null" :value="m.unit_price" /><span v-else>—</span></td>
                <td>
                  <span v-if="m.kind === 'design'" class="tag design">AH 购买</span>
                  <span v-else-if="m.price_source === 'npc'" class="tag npc">NPC 购买</span>
                  <span v-else-if="m.price_source === 'ah'" class="tag ah">拍卖行</span>
                  <span v-else class="muted">—</span>
                </td>
                <td class="num"><Money v-if="m.cost !== null" :value="m.cost" /><span v-else>—</span></td>
              </tr>
            </tbody>
          </table>

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

        <section class="panel">
          <h2>配方列表 · 点击操作</h2>
          <div class="flex flex-wrap" style="margin-bottom: 10px">
            <input v-model="recipeQuery" type="text" placeholder="搜索成品或材料名称…" style="width: 260px" />
            <span class="muted">共 {{ filteredRecipes.length }} 个配方参与计算</span>
          </div>
          <div style="overflow-x: auto">
            <table class="grid">
              <thead>
                <tr>
                  <th>成品</th>
                  <th>材料（单价/来源）</th>
                  <th class="num">材料费</th>
                  <th class="num">收入</th>
                  <th class="num">净成本</th>
                  <th>产物处置</th>
                  <th>技能档</th>
                  <th>来源</th>
                  <th>操作</th>
                </tr>
              </thead>
              <tbody>
                <tr v-for="r in filteredRecipes" :key="r.id"
                    :class="{ used: isUsed(r.id) }">
                  <td>
                    <span class="flex" style="gap: 6px">
                      <ItemIcon :icon="r.product_icon" :name="r.product_name" :size="24" />
                      <span>{{ r.product_name }}</span>
                    </span>
                    <span v-if="r.product_qty > 1" class="muted"> ×{{ r.product_qty }}</span>
                    <span v-if="r.is_new" class="tag new">新</span>
                    <span v-if="r.product_kind === 'enchant'" class="tag trainer">附魔</span>
                  </td>
                  <td>
                    <div v-for="m in r.materials" :key="m.item_id" class="flex" style="gap: 4px">
                      <ItemIcon :icon="m.icon" :name="m.name" :size="20" />
                      <span>{{ m.name }} ×{{ m.qty }}</span>
                      <span v-if="m.unit_price !== null" class="money muted">
                        <Money :value="m.unit_price" :size="11" />
                        <span class="tag" :class="m.price_source === 'npc' ? 'npc' : 'ah'">
                          {{ m.price_source === "npc" ? "NPC" : "拍卖" }}
                        </span>
                      </span>
                      <span v-else class="neg">无价格</span>
                      <span v-if="m.npc_limited" class="tag limited"
                            title="NPC 限量供应（如草药），已按拍卖行计价">限量</span>
                      <button class="btn small danger" @click="onBlockItem(m.item_id)"
                              :title="'屏蔽后，所有需要「' + m.name + '」的配方都不参与计算'">屏蔽</button>
                    </div>
                  </td>
                  <td class="num"><Money v-if="r.mat_cost !== null" :value="r.mat_cost" /><span v-else>—</span></td>
                  <td class="num"><Money v-if="r.revenue !== null" :value="r.revenue" /><span v-else>—</span></td>
                  <td class="num" :class="r.net_cost !== null && r.net_cost < 0 ? 'pos' : ''">
                    <Money v-if="r.net_cost !== null" :value="r.net_cost" /><span v-else>—</span>
                  </td>
                  <td>
                    <select style="width: 92px" :value="session.recipeDispositionOf(r.id)"
                            @change="onDispChange(r.id, $event)"
                            title="该配方产物的去向；「跟随全局」用左侧默认处置">
                      <option value="">跟随全局</option>
                      <option value="sell_ah">拍卖行</option>
                      <option value="sell_npc">卖店</option>
                      <option value="self_use">自用</option>
                    </select>
                  </td>
                  <td class="money">
                    {{ r.skill_orange }} / {{ r.skill_yellow }} / {{ r.skill_green }} / {{ r.skill_gray }}
                  </td>
                  <td>
                    <span v-if="r.source_type === 'trainer'" class="tag trainer">训练师</span>
                    <span v-else-if="r.source_type === 'design'" class="tag design">设计图</span>
                    <span v-else class="tag trainer">{{ r.source_type }}</span>
                  </td>
                  <td style="white-space: nowrap">
                    <button class="btn small" :class="{ active: session.state.blockedRecipeIds.includes(r.id) }"
                            @click="session.toggleBlockRecipe(r.id)">
                      {{ session.state.blockedRecipeIds.includes(r.id) ? "已屏蔽" : "屏蔽" }}
                    </button>
                    <button class="btn small" :class="{ active: session.state.confirmedRecipeIds.includes(r.id) }"
                            @click="session.toggleConfirmRecipe(r.id)"
                            title="确认采用：路线中优先做这个（默认 1 次，可在左侧改次数）">
                      {{ session.state.confirmedRecipeIds.includes(r.id) ? "已确认" : "确认采用" }}
                    </button>
                    <span v-if="session.state.confirmedRecipeIds.includes(r.id)" class="flex" style="gap: 2px; display: inline-flex">
                      ×<input type="number" min="1" max="999" style="width: 52px"
                              :value="session.confirmedCountOf(r.id)"
                              @change="onCountChange(r.id, $event)"
                              title="制作次数（长 CD 配方按周期内可做次数填）" />
                    </span>
                  </td>
                </tr>
              </tbody>
            </table>
          </div>
        </section>
      </div>
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
  </template>
</template>

<script setup lang="ts">
import { computed, onMounted, ref } from "vue";
import { RouterLink } from "vue-router";
import { api } from "@/api/client";
import ItemIcon from "@/components/ItemIcon.vue";
import Money from "@/components/Money.vue";
import PriceImportDialog from "@/components/PriceImportDialog.vue";
import TemplateExportDialog from "@/components/TemplateExportDialog.vue";
import { useSessionStore } from "@/stores/session";
import type { CalcResult, Disposition, Profession, Recipe } from "@/types";

const session = useSessionStore();
const professions = ref<Profession[]>([]);
const recipes = ref<Recipe[]>([]);
const result = ref<CalcResult | null>(null);
const loading = ref(false);
const recipeQuery = ref("");

const fromSkill = ref(session.state.fromSkill);
const toSkill = ref(session.state.toSkill);
const priceMode = ref(session.state.priceMode);
const disposition = ref<Disposition>(session.state.disposition);
const includeDesigns = ref(session.state.includeDesigns);
const designCost = ref(session.state.designCost);
const probMode = ref(session.state.probMode);
const probOrange = ref(session.state.probOrange);
const probYellow = ref(session.state.probYellow);
const probGreen = ref(session.state.probGreen);

const showSave = ref(false);
const showImport = ref(false);
const showTemplate = ref(false);
const saveTitle = ref("");
const saveAuthor = ref("");
const saveNotes = ref("");
const savePublic = ref(true);

const profName = computed(() => professions.value.find((p) => p.key === session.state.professionKey)?.name ?? "");
const profIcon = computed(() => professions.value.find((p) => p.key === session.state.professionKey)?.icon ?? null);
const validRange = computed(() => toSkill.value > fromSkill.value);
const filteredRecipes = computed(() => {
  const q = recipeQuery.value.trim();
  if (!q) return recipes.value;
  return recipes.value.filter(
    (r) => r.product_name.includes(q) || r.materials.some((m) => m.name.includes(q))
  );
});
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
    disposition.value,
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

/** 档位几率展示：公式模式下段内衰减，显示 100%→80%；fixed 模式显示单一值。 */
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

function onDispChange(id: number, e: Event) {
  const v = (e.target as HTMLSelectElement).value as Disposition | "";
  session.setRecipeDisposition(id, v);
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
  session.setDisposition(disposition.value);
  session.setIncludeDesigns(includeDesigns.value);
  session.setDesignCost(designCost.value);
  session.setProbMode(probMode.value);
  session.setProb("orange", probOrange.value);
  session.setProb("yellow", probYellow.value);
  session.setProb("green", probGreen.value);
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
</style>
