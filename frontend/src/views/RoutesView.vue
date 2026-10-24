<template>
  <section class="panel">
    <h2>路线分享广场</h2>
    <p class="muted" style="margin: 0 0 10px">
      玩家保存并公开的冲级路线。选一条「采用」，会用它的参数（含屏蔽/确认设置）按你服务器的当前价格重新计算。
    </p>
    <div class="flex flex-wrap">
      <select v-model="profFilter" @change="loadRoutes">
        <option value="">全部专业</option>
        <option v-for="p in professions" :key="p.key" :value="p.key">{{ p.name }}</option>
      </select>
      <label class="field"><input type="checkbox" v-model="onlyMyServer" @change="loadRoutes" /> 只看我的服务器</label>
      <button class="btn" @click="loadRoutes">刷新</button>
    </div>

    <table class="grid" v-if="routes.length" style="margin-top: 10px">
      <thead>
        <tr>
          <th>标题</th><th>专业</th><th>服务器</th><th>作者</th>
          <th>区间</th><th>价格口径</th><th class="num">净成本</th><th>时间</th><th></th>
        </tr>
      </thead>
      <tbody>
        <tr v-for="r in routes" :key="r.id">
          <td><b>{{ r.title }}</b></td>
          <td>{{ r.profession_name }}</td>
          <td>{{ r.server_name }}</td>
          <td>{{ r.author ?? "匿名" }}</td>
          <td class="money">{{ r.from_skill }} → {{ r.to_skill }}</td>
          <td>{{ r.price_mode === "latest" ? "最新" : "中位数" }}</td>
          <td class="num money" :class="r.net_display.startsWith('-') ? 'pos' : 'neg'">{{ r.net_display }}</td>
          <td class="muted">{{ r.created_at ? new Date(r.created_at).toLocaleDateString("zh-CN") : "—" }}</td>
          <td><button class="btn small" @click="openDetail(r)">查看 / 采用</button></td>
        </tr>
      </tbody>
    </table>
    <div v-else class="empty">还没有公开路线，去「冲级计划」保存一条吧。</div>
  </section>

  <div v-if="detail" class="save-mask" @click.self="detail = null">
    <div class="save-dialog panel">
      <h2>{{ detail.title }}</h2>
      <div class="muted">
        {{ detail.profession.name }} · {{ detail.server.name }} · {{ detail.params.from_skill }} → {{ detail.params.to_skill }}
        · 作者 {{ detail.author ?? "匿名" }}
      </div>
      <div v-if="detail.notes" style="margin-top: 6px">备注：{{ detail.notes }}</div>

      <div class="summary-cards">
        <div class="card"><div class="k">总制作</div><div class="v">{{ detail.totals.crafts }}</div></div>
        <div class="card"><div class="k">净成本</div><div class="v money">{{ detail.totals.net_display }}</div></div>
        <div class="card"><div class="k">分享码</div><div class="v" style="font-size: 14px">{{ detail.share_code }}</div></div>
      </div>

      <h3>路线步骤</h3>
      <table class="grid" v-if="detail.steps.length">
        <thead>
          <tr><th>技能区间</th><th>制作</th><th class="num">次数</th><th>档位</th><th class="num">净成本</th></tr>
        </thead>
        <tbody>
          <tr v-for="(s, i) in detail.steps" :key="i">
            <td class="money">{{ s.skill_from }} → {{ s.skill_to }}</td>
            <td>
              <span class="flex" style="gap: 6px">
                <ItemIcon :icon="s.product_icon" :name="s.recipe_name" :size="22" />
                <span>{{ s.recipe_name }}</span>
              </span>
            </td>
            <td class="num">{{ s.crafts }}</td>
            <td>{{ s.band === "orange" ? "橙" : s.band === "yellow" ? "黄" : "绿" }} {{ Math.round(s.prob * 100) }}%</td>
            <td class="num money" :class="s.net < 0 ? 'pos' : ''">{{ fmt(s.net) }}</td>
          </tr>
        </tbody>
      </table>

      <h3>材料清单</h3>
      <table class="grid" v-if="detail.materials.length">
        <thead><tr><th>材料</th><th class="num">数量</th><th class="num">小计</th></tr></thead>
        <tbody>
          <tr v-for="m in detail.materials" :key="m.item_id">
            <td>
              <span class="flex" style="gap: 6px">
                <ItemIcon :icon="m.icon" :name="m.name" :size="22" />
                <span>{{ m.name }}</span>
              </span>
            </td><td class="num">{{ m.qty }}</td>
            <td class="num money">{{ m.cost !== null ? fmt(m.cost) : "—" }}</td>
          </tr>
        </tbody>
      </table>

      <div class="flex" style="margin-top: 14px">
        <button class="btn primary" @click="onAdopt">采用此路线（按我的价格重算）</button>
        <button class="btn" @click="detail = null">关闭</button>
      </div>
      <div v-if="recalc" class="alert info" style="margin-top: 10px">
        按你服务器当前价格重算：总制作 {{ recalc.totals.crafts }} 次，净成本 {{ recalc.totals.net_display }}
        （保存时为 {{ detail.totals.net_display }}）。参数与屏蔽/确认设置已载入冲级计划页。
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { onMounted, ref } from "vue";
import { useRouter } from "vue-router";
import { api } from "@/api/client";
import ItemIcon from "@/components/ItemIcon.vue";
import { useSessionStore } from "@/stores/session";
import type { CalcResult, Profession, RouteDetail, RouteListItem } from "@/types";

const session = useSessionStore();
const router = useRouter();
const routes = ref<RouteListItem[]>([]);
const professions = ref<Profession[]>([]);
const profFilter = ref("");
const onlyMyServer = ref(false);
const detail = ref<RouteDetail | null>(null);
const recalc = ref<CalcResult | null>(null);

onMounted(async () => {
  professions.value = await api.listProfessions();
  await loadRoutes();
});

async function loadRoutes() {
  routes.value = await api.listRoutes({
    profession_key: profFilter.value || undefined,
    server_id: onlyMyServer.value ? session.state.serverId ?? undefined : undefined,
    public_only: true,
  });
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

async function openDetail(r: RouteListItem) {
  detail.value = await api.routeDetail(r.share_code);
  recalc.value = null;
}

async function onAdopt() {
  if (!detail.value) return;
  if (!session.state.serverId) {
    alert("请先选择服务器");
    return;
  }
  session.setServer(detail.value.server.id, detail.value.server.name);
  session.setProfession(detail.value.profession.key);
  session.applyParams(detail.value.params);
  recalc.value = await api.routeRecalc(detail.value.share_code);
  router.push("/plan");
}
</script>

<style scoped>
.save-mask {
  position: fixed; inset: 0; background: rgba(30, 25, 15, 0.45);
  display: flex; align-items: center; justify-content: center; z-index: 50;
}
.save-dialog { width: 720px; max-width: 94vw; max-height: 86vh; overflow: auto; }
</style>
