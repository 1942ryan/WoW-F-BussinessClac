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
      </div>

      <div class="param-row">
        <span class="pill">已屏蔽配方 {{ session.state.blockedRecipeIds.length }}</span>
        <span class="pill">已屏蔽物品 {{ session.state.blockedItemIds.length }}</span>
        <span class="pill">确认采用 {{ session.state.confirmedRecipeIds.length }}</span>
        <button class="btn small" @click="onClearOverrides">清空全部屏蔽/确认</button>
      </div>

      <!-- 云价格有效期：恒定一行，不随操作出现/消失（防抖动） -->
      <div class="fresh-row" :class="{ stale: freshness?.stale, empty: !freshness?.item_count }">
        <template v-if="!freshness || !freshness.item_count">
          <span class="fk">价格数据</span>
          <span>本服还没有导入过拍卖行价格，当前只能按 NPC 卖店价估算。</span>
          <RouterLink class="flink" to="/import">去导价 →</RouterLink>
        </template>
        <template v-else>
          <span class="fk">价格数据</span>
          <span v-if="freshness.stale">⚠ 最近一次导入是 <b>{{ ageText(freshness.age_hours) }}</b>，已超过 {{ freshness.valid_hours }} 小时有效期</span>
          <span v-else>最近一次导入 <b>{{ ageText(freshness.age_hours) }}</b>，有效期 {{ freshness.valid_hours }} 小时</span>
          <span class="fsep">·</span>
          <span>覆盖 {{ freshness.item_count }} 个物品</span>
          <template v-if="freshness.stale_items">
            <span class="fsep">·</span>
            <span class="fwarn">其中 {{ freshness.stale_items }} 个物品的报价已过期</span>
          </template>
          <RouterLink class="flink" to="/import">重新导价 →</RouterLink>
        </template>
      </div>

      <p class="muted rules-note">
        计算规则已固定：涨点按 WoW 客户端公式（橙档 100%，黄/绿档 =(灰档−当前)/(灰档−黄档) 递减）；
        成品默认卖拍卖行，可在下方配方列表逐条改「卖店」；设计图配方自动计入，图纸按拍卖行价一次性计入成本。
      </p>
    </section>

    <!-- ============ 主体：左 3/4 配方列表，右 1/4 计算结果 ============ -->
    <div class="plan-body">
      <!-- 左栏：配方列表 -->
      <section class="panel plan-recipes">
        <h2>配方列表</h2>
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
                <th class="wrap">材料（单价）</th>
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
                <td class="prod-cell">
                  <div class="prod-line">
                    <ItemIcon :icon="r.product_icon" :name="r.product_name" :size="24"
                              :item-id="r.product_item_id">
                      <span class="prod-name">{{ r.product_name }}</span>
                    </ItemIcon>
                    <span v-if="r.product_qty > 1" class="muted">×{{ r.product_qty }}</span>
                    <span v-if="r.is_new" class="tag new">新</span>
                    <span v-if="r.has_cooldown" class="tag cd"
                          title="有冷却时间：一个 CD 周期只能做一次，确认采用时默认次数为 1">CD</span>
                    <span v-if="r.product_kind === 'enchant'" class="tag trainer">附魔</span>
                    <span v-if="r.revenue_fallback" class="tag noah"
                          title="拍卖行查不到这个成品的价格，收入已按 NPC 卖店价估算（通常是冷门配方）。不想做就点 ⊘ 屏蔽它">AH无价</span>
                  </div>
                </td>
                <td class="wrap">
                  <div v-for="m in r.materials" :key="m.item_id" class="flex" style="gap: 4px">
                    <ItemIcon :icon="m.icon" :name="m.name" :size="20" :item-id="m.item_id">
                      <span>{{ m.name }} ×{{ m.qty }}</span>
                    </ItemIcon>
                    <span v-if="m.unit_price !== null" class="money muted">
                      <Money :value="m.unit_price" :size="11" />
                    </span>
                    <span v-else class="neg">无价格</span>
                    <button class="btn small icon-btn" @click="onBlockItem(m.item_id)"
                            :title="'屏蔽后，所有需要「' + m.name + '」的配方都不参与计算'">
                      <span class="ico ban">⊘</span>
                    </button>
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
                            title="卖给拍卖行（价 = 当前有效拍卖价扣 5% 手续费的到手价；到手低于卖店时按卖店计）">
                      <span class="pb-k">拍卖行</span>
                      <Money v-if="r.product_ah_price !== null"
                             :value="r.product_ah_net ?? r.product_ah_price" :size="12" />
                      <span v-else class="muted">无价</span>
                    </button>
                    <span v-if="r.revenue_npc_better" class="tag npc"
                          title="拍卖行有价，但扣完 5% 手续费到手价低于卖店价，收入已按卖店价计算">
                      按卖店
                    </span>
                    <button v-if="session.recipeDispositionOf(r.id)" class="price-btn ghost"
                            @click="onDispChange(r.id, '')" title="清除本配方覆盖，回到跟随全局（卖拍卖行）">↺</button>
                  </div>
                </td>
                <td class="skill-bands">
                  <span class="sb sb-o">{{ r.skill_orange }}</span>
                  <span class="sb sb-y">{{ r.skill_yellow }}</span>
                  <span class="sb sb-g">{{ r.skill_green }}</span>
                  <span class="sb sb-r">{{ r.skill_gray }}</span>
                </td>
                <td>
                  <span class="src-cell" @mouseenter="onSrcEnter($event, r)" @mouseleave="onSrcLeave">
                    <span v-if="r.source_type === 'trainer'" class="tag trainer">训练师</span>
                    <span v-else-if="r.source_type === 'design'" class="tag design">设计图</span>
                    <span v-else class="tag trainer">{{ r.source_type }}</span>
                    <span v-if="r.vendor_favor" class="tag camp">营地 {{ r.vendor_favor }}</span>
                  </span>
                </td>
                <td class="num">
                  <Money v-if="r.net_cost !== null" :value="r.net_cost" neg-as-earn />
                  <span v-else>—</span>
                </td>
                <td class="op-col">
                  <button class="btn small icon-btn"
                          :class="{ active: session.state.blockedRecipeIds.includes(r.id) }"
                          @click="onBlockRecipe(r.id)"
                          :title="session.state.blockedRecipeIds.includes(r.id)
                            ? '已屏蔽，点击恢复参与计算'
                            : '屏蔽此配方，不参与计算'">
                    <span class="ico ban">⊘</span>
                  </button>
                  <button class="btn small icon-btn"
                          :class="{ active: session.state.confirmedRecipeIds.includes(r.id) }"
                          @click="onConfirmRecipe(r)"
                          :title="session.state.confirmedRecipeIds.includes(r.id)
                            ? '已确认：优先做这个配方。后面的数字是次数上限，留空=不限（点击取消）'
                            : (r.has_cooldown
                                ? '确认采用：有 CD 的配方默认只做 1 次'
                                : '确认采用：默认不限次数，优先做它直到没有更划算的配方')">
                    <span class="ico star">{{ session.state.confirmedRecipeIds.includes(r.id) ? "★" : "☆" }}</span>
                    <span v-if="session.state.confirmedRecipeIds.includes(r.id)" class="max-tag">最大</span>
                  </button>
                  <span v-if="session.state.confirmedRecipeIds.includes(r.id)" class="cnt-wrap">
                    <input type="number" min="0" max="999" class="cnt-input"
                           :value="session.confirmedCountOf(r.id) || ''"
                           placeholder="不限"
                           @change="onCountChange(r.id, $event)"
                           :title="r.has_cooldown
                             ? '有 CD：一个周期只能做几次就填几次（默认 1）'
                             : '次数上限，留空 = 不限（由算法自己冲到收益最大的次数）'" />
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

        <!-- 口径说明：恒定显示一行，避免随处置方式切换而抖动 -->
        <div class="calc-note">
          成交收入按拍卖行<strong>到手价</strong>计算：已扣
          {{ Math.round(result.totals.ah_cut_rate * 100) }}% 手续费
          <template v-if="result.totals.ah_cut > 0">
            （本路线共 <Money :value="result.totals.ah_cut" :size="11" />）
          </template>
          ；查不到拍卖价、或到手价低于卖店价时，自动按<strong>卖店价</strong>计。
        </div>

        <!-- 材料采购清单入口（点开为右侧抽屉） -->
        <div class="flex flex-wrap" style="margin: 10px 0; gap: 8px">
          <button class="btn primary" @click="showShopping = true"
                  :disabled="!result.materials.length"
                  title="本次路线的材料采购清单">
            材料采购清单<template v-if="result.materials.length">（{{ result.materials.length }}）</template>
          </button>
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
                <th class="num">花费</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="(s, i) in result.steps" :key="i">
                <td class="money">{{ Math.round(s.skill_from) }} → {{ Math.round(s.skill_to) }}</td>
                <td>
                  <ItemIcon :icon="s.product_icon" :name="s.recipe_name" :size="24"
                            :item-id="s.product_item_id">
                    <span>{{ s.recipe_name }}</span>
                  </ItemIcon>
                  <span v-if="s.confirmed" class="tag confirmed">确认采用</span>
                  <span v-if="s.disposition" class="tag disp">{{ dispLabel(s.disposition) }}</span>
                  <span v-if="s.revenue_fallback" class="tag noah"
                        title="拍卖行查不到这个成品的价格，本步收入按 NPC 卖店价估算。冷门配方建议在左侧 ⊘ 屏蔽后重算">AH无价</span>
                  <span v-else-if="s.revenue_npc_better" class="tag npc"
                        title="本步成品的拍卖行到手价低于卖店价，收入已按卖店价计算">按卖店</span>
                  <span v-if="s.design_cost" class="tag design" :title="'设计图：' + (s.design_name ?? '')">
                    图纸 <Money :value="s.design_cost" :size="11" />
                  </span>
                  <span v-if="s.vendor_favor" class="tag camp"
                        :title="'贸易营地图纸，需 ' + s.vendor_favor + ' 点商人青睐（不是声望，靠上板条箱获得）'">
                    营地 {{ s.vendor_favor }}
                  </span>
                </td>
                <td class="num">{{ Math.round(s.crafts) }}</td>
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
                  <ItemIcon :icon="m.icon" :name="m.name" :size="22" :item-id="m.item_id">
                    <span>{{ m.name }}</span>
                  </ItemIcon>
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

    <!-- 保存成功 → 直接给一条可复制的链接（别人点开就是这条路线） -->
    <div v-if="shareLink" class="save-mask" @click.self="shareLink = ''">
      <div class="save-dialog panel">
        <h2>路线已保存</h2>
        <p class="muted" style="margin: 0 0 10px">
          把这条链接发给别人，点开就能直接看到整条路线（每一步做什么、做几次、花多少）。
        </p>
        <div class="flex" style="gap: 8px">
          <input ref="linkInput" type="text" :value="shareLink" readonly style="flex: 1; min-width: 0" />
          <button class="btn primary" @click="copyShareLink">{{ copied ? "已复制 ✓" : "复制链接" }}</button>
        </div>
        <div class="flex" style="margin-top: 12px; gap: 8px">
          <a class="btn" :href="shareLink" target="_blank" rel="noopener">打开看看</a>
          <button class="btn" @click="shareLink = ''">关闭</button>
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
    <SourceTip :text="srcTip?.text ?? null" :visible="!!srcTip" :anchor="srcTip?.anchor ?? null" />
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
import SourceTip from "@/components/SourceTip.vue";
import TemplateExportDialog from "@/components/TemplateExportDialog.vue";
import { useSessionStore } from "@/stores/session";
import type { CalcResult, Disposition, PriceFreshness, Profession, Recipe } from "@/types";

const session = useSessionStore();
const professions = ref<Profession[]>([]);
const recipes = ref<Recipe[]>([]);
const result = ref<CalcResult | null>(null);
/** 云价格新鲜度：显示在本服哪次导价、有效期多久、多少条已过期 */
const freshness = ref<PriceFreshness | null>(null);
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
/** 保存成功后生成的分享链接（弹窗展示 + 一键复制） */
const shareLink = ref("");
const copied = ref(false);
/** 来源列悬停浮层（共享一个实例，避免 400+ 行各建一个） */
const srcTip = ref<{ text: string; anchor: HTMLElement } | null>(null);

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

onMounted(async () => {
  professions.value = await api.listProfessions();
  if (session.state.serverId && session.state.professionKey) {
    await loadRecipes();
  }
  await loadFreshness();
});

/** 云价格有效期（本服最近一次导入时间 / 过期条数）。 */
async function loadFreshness() {
  if (!session.state.serverId) return;
  try {
    freshness.value = await api.priceFreshness(session.state.serverId);
  } catch {
    freshness.value = null;
  }
}

/** 距今多久：<1 小时按分钟，<48 小时按小时，再长按天。 */
function ageText(hours: number | null | undefined): string {
  if (hours === null || hours === undefined) return "从未导入";
  if (hours < 1) return `${Math.max(1, Math.round(hours * 60))} 分钟前`;
  if (hours < 48) return `${Math.round(hours)} 小时前`;
  return `${Math.round(hours / 24)} 天前`;
}

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

function onSrcEnter(e: Event, r: Recipe) {
  srcTip.value = {
    text: r.source_detail ?? r.source_type,
    anchor: e.currentTarget as HTMLElement,
  };
}

function onSrcLeave() {
  srcTip.value = null;
}

function dispLabel(d: string) {
  return d === "sell_ah" ? "→拍卖" : d === "sell_npc" ? "→卖店" : "→自用";
}

/** 当前生效处置：单配方覆盖优先，否则跟随全局（全局固定为卖拍卖行）。 */
function curDisp(r: Recipe): Disposition {
  return (session.recipeDispositionOf(r.id) as Disposition) || "sell_ah";
}

/** 计算序号：连续改动会并发多次重算，只接受最后一次请求的结果，避免旧响应覆盖新响应。 */
let calcSeq = 0;

async function doCalc() {
  if (!validRange.value) return;
  const seq = ++calcSeq;
  loading.value = true;
  try {
    const r = await api.calc(session.toCalcParams());
    if (seq === calcSeq) result.value = r;
  } finally {
    if (seq === calcSeq) loading.value = false;
  }
}

/** 已有计算结果时立即按最新参数重算（任何屏蔽/确认/处置/次数改动后调用）。 */
async function recalcNow() {
  if (!result.value) return;
  await doCalc();
}

async function onDispChange(id: number, d: Disposition | "") {
  session.setRecipeDisposition(id, d);
  await loadRecipes();
  await recalcNow();
}

function onBlockRecipe(id: number) {
  session.toggleBlockRecipe(id);
  recalcNow();
}

function onConfirmRecipe(r: Recipe) {
  session.toggleConfirmRecipe(r.id, !!r.has_cooldown);
  recalcNow();
}

function onCountChange(id: number, e: Event) {
  const raw = (e.target as HTMLInputElement).value.trim();
  const v = raw === "" ? 0 : Number(raw);
  session.setConfirmedCount(id, Number.isFinite(v) ? v : 0); // 0 = 不限次
  recalcNow();
}

function onBlockItem(itemId: number) {
  session.toggleBlockItem(itemId);
  recalcNow();
}

function onClearOverrides() {
  session.clearOverrides();
  loadRecipes();
  recalcNow();
}

async function runCalc() {
  if (!validRange.value) return;
  session.setRange(fromSkill.value, toSkill.value);
  session.setPriceMode(priceMode.value);
  await loadRecipes();
  await doCalc();
}

/** 价格导入完成后：刷新配方价格，已有计算结果时自动重算。 */
async function onImported() {
  showImport.value = false;
  await Promise.all([loadRecipes(), loadFreshness()]);
  await recalcNow();
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
  shareLink.value = `${location.origin}/r/${detail.share_code}`;
  copied.value = false;
}

/** 复制分享链接：优先 Clipboard API，非安全上下文退回隐藏 textarea + execCommand。 */
async function copyShareLink() {
  const text = shareLink.value;
  try {
    await navigator.clipboard.writeText(text);
  } catch {
    const ta = document.createElement("textarea");
    ta.value = text;
    ta.style.position = "fixed";
    ta.style.opacity = "0";
    document.body.appendChild(ta);
    ta.select();
    document.execCommand("copy");
    ta.remove();
  }
  copied.value = true;
  window.setTimeout(() => (copied.value = false), 1800);
}
</script>

<style scoped>
/* 口径说明：拍卖行手续费扣除（恒定一行，不随处置方式切换而出现/消失） */
.calc-note {
  margin: 6px 0 0;
  font-size: 11.5px;
  line-height: 1.55;
  color: var(--muted, #7a7264);
}
.calc-note strong {
  color: var(--text, #3a3327);
  font-weight: 600;
}
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
/* 云价格有效期一行：恒定存在（含空数据态），避免切换时上下抖动 */
.fresh-row {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 6px;
  margin-top: 10px;
  padding: 6px 10px;
  border-radius: 6px;
  background: rgba(128, 128, 128, 0.08);
  font-size: 12px;
  line-height: 1.5;
  color: var(--muted, #7a7264);
}
.fresh-row.stale {
  background: rgba(192, 57, 43, 0.09);
  color: #a03030;
}
.fresh-row .fk {
  font-weight: 600;
  color: var(--text, #3a3327);
}
.fresh-row.stale .fk {
  color: #a03030;
}
.fresh-row b {
  color: var(--text, #3a3327);
}
.fresh-row.stale b {
  color: #a03030;
}
.fresh-row .fsep { color: rgba(128, 128, 128, 0.55); }
.fresh-row .fwarn { color: #a03030; }
.fresh-row .flink {
  margin-left: auto;
  color: #8a6100;
  text-decoration: none;
  white-space: nowrap;
}
.fresh-row .flink:hover { text-decoration: underline; }
.rules-note {
  margin: 10px 0 0;
  font-size: 12px;
  line-height: 1.6;
}
.disp-btns {
  display: flex;
  flex-wrap: wrap;
  gap: 4px;
}
/* ---- 成品列：图标 + 名称 + 数量/标记 全在一行 ----
   之前这些标记写在 flex 容器外面，会被当成块级内容挤到第二行（1080P 下尤其明显） */
.prod-cell { white-space: nowrap; }
.prod-line {
  display: flex;
  align-items: center;
  gap: 6px;
  flex-wrap: nowrap;
}
.prod-name { overflow: hidden; text-overflow: ellipsis; }
/* ---- 技能档：竖排 + 橙黄绿灰上色 ---- */
.skill-bands {
  display: flex;
  flex-direction: column;
  gap: 1px;
  font-size: 12px;
  line-height: 1.3;
  white-space: nowrap;
  font-variant-numeric: tabular-nums;
}
.sb { font-weight: 600; }
.sb-o { color: #c2610f; }
.sb-y { color: #a8831b; }
.sb-g { color: #4d7d36; }
.sb-r { color: #8a8a8a; }
/* ---- 图标操作按钮（星标=确认采用/最大，禁令=屏蔽） ---- */
/* ---- 操作列：固定宽度 + 控件等高，避免「确认」出现/取消时整表重排 ---- */
/* 宽度按「⊘ + ★最大 + ×999」撑满后的实测值留余量，避免确认状态切换时列宽抖动 */
.op-col {
  white-space: nowrap;
  width: 152px;
  min-width: 152px;
  max-width: 152px;
  vertical-align: middle;
}
.cnt-wrap {
  display: inline-flex;
  align-items: center;
  gap: 2px;
  margin-left: 2px;
}
.cnt-wrap::before {
  content: "×";
  color: var(--muted);
  font-size: 12px;
}
/* 来源列：悬停弹详情浮层 */
.src-cell {
  cursor: help;
  display: inline-block;
}
.cnt-input {
  width: 38px;
  height: 22px;
  padding: 0 3px;
  font-size: 12px;
  line-height: 20px;
}
/* ---- 窄屏（1080P 常见缩放后视口 1366~1600）压缩表格，避免材料名折行 ---- */
.plan-recipes td.wrap .flex { white-space: nowrap; }
@media (max-width: 1600px) {
  .plan-recipes table.grid { font-size: 12px; }
  .plan-recipes table.grid th { padding: 6px 6px; }
  .plan-recipes table.grid td { padding: 5px 6px; }
  .skill-bands { font-size: 11px; }
  .op-col {
    width: 140px;
    min-width: 140px;
    max-width: 140px;
  }
  .icon-btn { padding: 3px 5px; }
  .max-tag { font-size: 10px; }
  .cnt-input { width: 34px; }
}
.icon-btn {
  display: inline-flex;
  align-items: center;
  gap: 3px;
  padding: 3px 7px;
}
.icon-btn .ico { font-size: 13px; line-height: 1; }
.icon-btn .ban { color: #a03030; }
.icon-btn.active .ban { color: #c0392b; }
.icon-btn .star { color: #b08630; }
.icon-btn.active .star { color: #d8a53a; }
.max-tag { font-size: 11px; font-weight: 700; color: #8a6100; }
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
