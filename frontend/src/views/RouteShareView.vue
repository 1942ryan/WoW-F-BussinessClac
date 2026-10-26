<template>
  <section v-if="error" class="panel">
    <h2>路线不存在</h2>
    <p class="muted">{{ error }}</p>
    <RouterLink class="btn primary" to="/routes">去路线广场</RouterLink>
  </section>

  <section v-else-if="!detail" class="panel">
    <div class="empty">正在加载路线…</div>
  </section>

  <template v-else>
    <section class="panel">
      <h2>
        <span class="flex" style="gap: 8px; align-items: center">
          {{ detail.title }}
          <span class="tag design">{{ detail.profession.name }}</span>
        </span>
      </h2>
      <div class="muted flex flex-wrap" style="gap: 10px">
        <span class="flex" style="gap: 4px">
          <FactionIcon v-if="detail.server.faction && detail.server.faction !== 'both'"
                       :faction="detail.server.faction" :size="16" />
          {{ detail.server.name }}
        </span>
        <span>{{ detail.params.from_skill }} → {{ detail.params.to_skill }}</span>
        <span>作者 {{ detail.author ?? "匿名" }}</span>
        <span>价格口径 {{ detail.params.price_mode === "latest" ? "最新" : "中位数" }}</span>
        <span v-if="detail.created_at">{{ new Date(detail.created_at).toLocaleDateString("zh-CN") }}</span>
      </div>
      <div v-if="detail.notes" style="margin-top: 8px">备注：{{ detail.notes }}</div>

      <div class="summary-cards">
        <div class="card">
          <div class="k">总制作次数</div>
          <div class="v">{{ Math.round(detail.totals.crafts) }}</div>
        </div>
        <div class="card">
          <div class="k">花费</div>
          <div class="v"><Money :value="detail.totals.net" :size="14" neg-as-earn /></div>
        </div>
        <div class="card">
          <div class="k">路线来源</div>
          <div class="v" style="font-size: 13px">
            {{ mine ? "你保存的这条" : "别人分享的" }}
          </div>
        </div>
      </div>

      <div class="flex flex-wrap" style="margin: 12px 0; gap: 8px">
        <button class="btn primary" @click="onAdopt" :disabled="!session.state.serverId">
          用我服务器的价格重算
        </button>
        <button class="btn" @click="copyLink">{{ copied ? "已复制 ✓" : "复制链接" }}</button>
        <RouterLink class="btn" to="/routes">返回广场</RouterLink>
      </div>
      <div v-if="!session.state.serverId" class="alert info" style="margin-top: 0">
        想按自己服务器的价格重算，请先回首页选一个服务器。
      </div>

      <h3>路线步骤</h3>
      <div style="overflow-x: auto">
        <table class="grid nowrap" v-if="detail.steps.length">
          <thead>
            <tr>
              <th>技能区间</th><th>制作</th><th class="num">次数</th>
              <th class="num">材料</th><th class="num">收入</th><th class="num">花费</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="(s, i) in detail.steps" :key="i">
              <td class="money">{{ Math.round(s.skill_from) }} → {{ Math.round(s.skill_to) }}</td>
              <td>
                <ItemIcon :icon="s.product_icon" :name="s.recipe_name" :size="22"
                          :item-id="s.product_item_id">
                  <span>{{ s.recipe_name }}</span>
                </ItemIcon>
                <span v-if="s.confirmed" class="tag confirmed">确认采用</span>
                <span v-if="s.revenue_fallback" class="tag noah">AH无价</span>
                <span v-else-if="s.revenue_npc_better" class="tag npc">按卖店</span>
                <span v-if="s.vendor_favor" class="tag camp">营地 {{ s.vendor_favor }}</span>
              </td>
              <td class="num">{{ s.crafts ? Math.round(s.crafts) : "—" }}</td>
              <td class="num money"><Money :value="s.mat_cost" /></td>
              <td class="num money"><Money :value="s.revenue" neg-as-earn /></td>
              <td class="num money"><Money :value="s.net" neg-as-earn /></td>
            </tr>
          </tbody>
        </table>
        <div v-else class="empty">这条路线没有可展示的步骤。</div>
      </div>

      <h3>材料清单</h3>
      <div style="overflow-x: auto">
        <table class="grid nowrap" v-if="detail.materials.length">
          <thead><tr><th>材料</th><th class="num">数量</th><th class="num">单价</th><th class="num">小计</th></tr></thead>
          <tbody>
            <tr v-for="m in detail.materials" :key="m.item_id">
              <td>
                <ItemIcon :icon="m.icon" :name="m.name" :size="22" :item-id="m.item_id">
                  <span>{{ m.name }}</span>
                </ItemIcon>
                <span v-if="m.kind === 'design'" class="tag design">设计图</span>
              </td>
              <td class="num">{{ Math.round(m.qty) }}</td>
              <td class="num"><Money v-if="m.unit_price !== null" :value="m.unit_price" /><span v-else>—</span></td>
              <td class="num money"><Money v-if="m.cost !== null" :value="m.cost" /><span v-else>—</span></td>
            </tr>
          </tbody>
        </table>
        <div v-else class="empty">这条路线没有保存材料清单。</div>
      </div>
    </section>
  </template>
</template>

<script setup lang="ts">
/**
 * 分享链接落地页 /r/{share_code}
 *
 * 别人点开链接就直接看到整条路线（不像广场那样要自己找），并且可以一键
 * 「按我服务器的价格重算」把参数与屏蔽/确认设置带进冲级计划页。
 */
import { computed, onMounted, ref } from "vue";
import { RouterLink, useRoute, useRouter } from "vue-router";
import { api } from "@/api/client";
import FactionIcon from "@/components/FactionIcon.vue";
import ItemIcon from "@/components/ItemIcon.vue";
import Money from "@/components/Money.vue";
import { useSessionStore } from "@/stores/session";
import type { Faction, RouteDetail } from "@/types";

const route = useRoute();
const router = useRouter();
const session = useSessionStore();
const detail = ref<RouteDetail | null>(null);
const error = ref("");
const copied = ref(false);

const code = computed(() => String(route.params.code ?? ""));
const mine = computed(
  () => !!detail.value && session.state.serverId === detail.value.server.id
);

onMounted(async () => {
  try {
    detail.value = await api.routeDetail(code.value);
  } catch {
    error.value = "链接里的分享码找不到对应路线，可能已被删除或链接不完整。";
  }
});

async function onAdopt() {
  if (!detail.value || !session.state.serverId) return;
  session.setServer(
    detail.value.server.id,
    detail.value.server.name,
    (detail.value.server.faction as Faction) ?? "both"
  );
  session.setProfession(detail.value.profession.key);
  session.applyParams(detail.value.params);
  router.push("/plan");
}

async function copyLink() {
  const url = `${location.origin}/r/${code.value}`;
  try {
    await navigator.clipboard.writeText(url);
  } catch {
    const ta = document.createElement("textarea");
    ta.value = url;
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
