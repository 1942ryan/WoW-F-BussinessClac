<template>
  <div v-if="!session.state.serverId" class="panel">
    <div class="alert warn">请先回到首页选择服务器。</div>
    <RouterLink class="btn primary" to="/">去选择服务器</RouterLink>
  </div>

  <template v-else>
    <section class="panel">
      <h2>计算参数 · {{ profName }}</h2>
      <div class="flex flex-wrap" style="gap: 16px">
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
        <label class="field">成品处置
          <select v-model="disposition">
            <option value="sell_ah">卖给拍卖行</option>
            <option value="sell_npc">卖给 NPC</option>
            <option value="self_use">自用（不计收入）</option>
          </select>
        </label>
        <label class="field">
          <input type="checkbox" v-model="includeDesigns" /> 含设计图配方（掉落/购买图纸）
        </label>
        <button class="btn primary" @click="runCalc" :disabled="loading || !validRange">
          {{ loading ? "计算中…" : "计算路线" }}
        </button>
      </div>
      <div class="flex flex-wrap" style="margin-top: 10px">
        <span class="pill">已屏蔽配方 {{ session.state.blockedRecipeIds.length }}</span>
        <span class="pill">已屏蔽物品 {{ session.state.blockedItemIds.length }}</span>
        <span class="pill">确认采用 {{ session.state.confirmedRecipeIds.length }}</span>
        <button class="btn small" @click="onClearOverrides">清空全部屏蔽/确认</button>
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
              <th>技能档</th>
              <th>来源</th>
              <th>操作</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="r in filteredRecipes" :key="r.id"
                :class="{ used: isUsed(r.id) }">
              <td>
                <span :class="'q' + (r.product_item_id ? qualityOf(r) : 1)">{{ r.product_name }}</span>
                <span v-if="r.product_qty > 1" class="muted"> ×{{ r.product_qty }}</span>
                <span v-if="r.is_new" class="tag new">新</span>
                <span v-if="r.product_kind === 'enchant'" class="tag trainer">附魔</span>
              </td>
              <td>
                <div v-for="m in r.materials" :key="m.item_id" class="flex" style="gap: 4px">
                  <span>{{ m.name }} ×{{ m.qty }}</span>
                  <span v-if="m.unit_price !== null" class="money muted">
                    {{ fmt(m.unit_price) }}
                    <span class="tag" :class="m.price_source === 'npc' ? 'npc' : 'ah'">
                      {{ m.price_source === "npc" ? "NPC" : "拍卖" }}
                    </span>
                  </span>
                  <span v-else class="neg">无价格</span>
                  <button class="btn small danger" @click="onBlockItem(m.item_id)"
                          :title="'屏蔽后，所有需要「' + m.name + '」的配方都不参与计算'">屏蔽</button>
                </div>
              </td>
              <td class="num">{{ r.mat_cost !== null ? fmt(r.mat_cost) : "—" }}</td>
              <td class="num">{{ r.revenue !== null ? fmt(r.revenue) : "—" }}</td>
              <td class="num" :class="r.net_cost !== null && r.net_cost < 0 ? 'pos' : ''">
                {{ r.net_cost !== null ? fmt(r.net_cost) : "—" }}
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
                        title="确认采用：路线中优先做这个">
                  {{ session.state.confirmedRecipeIds.includes(r.id) ? "已确认" : "确认采用" }}
                </button>
              </td>
            </tr>
          </tbody>
        </table>
      </div>
    </section>

    <section class="panel" v-if="result">
      <h2>计算结果 · {{ result.profession.name }} {{ result.params.from_skill }} → {{ result.params.to_skill }}</h2>

      <div class="summary-cards">
        <div class="card"><div class="k">总制作次数</div><div class="v">{{ result.totals.crafts }}</div></div>
        <div class="card"><div class="k">材料花费</div><div class="v money">{{ fmt(result.totals.mat_cost) }}</div></div>
        <div class="card"><div class="k">成品收入</div><div class="v money pos">{{ fmt(result.totals.revenue) }}</div></div>
        <div class="card"><div class="k">净成本</div><div class="v money" :class="result.totals.net < 0 ? 'pos' : 'neg'">
          {{ result.totals.net_display }}
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
          </tr>
        </thead>
        <tbody>
          <tr v-for="(s, i) in result.steps" :key="i">
            <td class="money">{{ s.skill_from }} → {{ s.skill_to }}</td>
            <td>
              {{ s.recipe_name }}
              <span v-if="s.confirmed" class="tag confirmed">确认采用</span>
            </td>
            <td class="num">{{ s.crafts }}</td>
            <td>
              <span class="tag" :class="bandClass(s.band)">
                {{ bandLabel(s.band) }} {{ Math.round(s.prob * 100) }}%
              </span>
            </td>
            <td class="num">{{ fmt(s.mat_cost) }}</td>
            <td class="num">{{ fmt(s.revenue) }}</td>
            <td class="num" :class="s.net < 0 ? 'pos' : ''">{{ fmt(s.net) }}</td>
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
            <td>{{ m.name }}</td>
            <td class="num">{{ m.qty }}</td>
            <td class="num">{{ m.unit_price !== null ? fmt(m.unit_price) : "—" }}</td>
            <td>
              <span v-if="m.price_source === 'npc'" class="tag npc">NPC 购买</span>
              <span v-else-if="m.price_source === 'ah'" class="tag ah">拍卖行</span>
              <span v-else class="muted">—</span>
            </td>
            <td class="num">{{ m.cost !== null ? fmt(m.cost) : "—" }}</td>
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
  </template>
</template>

<script setup lang="ts">
import { computed, onMounted, ref } from "vue";
import { RouterLink } from "vue-router";
import { api } from "@/api/client";
import { useSessionStore } from "@/stores/session";
import type { CalcResult, Profession, Recipe } from "@/types";

const session = useSessionStore();
const professions = ref<Profession[]>([]);
const recipes = ref<Recipe[]>([]);
const result = ref<CalcResult | null>(null);
const loading = ref(false);
const recipeQuery = ref("");

const fromSkill = ref(session.state.fromSkill);
const toSkill = ref(session.state.toSkill);
const priceMode = ref(session.state.priceMode);
const disposition = ref(session.state.disposition);
const includeDesigns = ref(session.state.includeDesigns);

const showSave = ref(false);
const saveTitle = ref("");
const saveAuthor = ref("");
const saveNotes = ref("");
const savePublic = ref(true);

const profName = computed(() => professions.value.find((p) => p.key === session.state.professionKey)?.name ?? "");
const validRange = computed(() => toSkill.value > fromSkill.value);
const filteredRecipes = computed(() => {
  const q = recipeQuery.value.trim();
  if (!q) return recipes.value;
  return recipes.value.filter(
    (r) => r.product_name.includes(q) || r.materials.some((m) => m.name.includes(q))
  );
});

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
    disposition.value
  );
}

function isUsed(id: number) {
  return result.value?.steps.some((s) => s.recipe_id === id) ?? false;
}

function qualityOf(r: Recipe) {
  // 后端未返回品质字段，默认按名称无染色处理
  return 1;
}

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

function bandLabel(b: string) {
  return b === "orange" ? "橙" : b === "yellow" ? "黄" : "绿";
}
function bandClass(b: string) {
  return b === "orange" ? "band-o" : b === "yellow" ? "band-y" : "band-g";
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
  await loadRecipes();
  loading.value = true;
  try {
    result.value = await api.calc(session.toCalcParams());
  } finally {
    loading.value = false;
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
