<template>
  <div>
    <section class="panel">
      <h2>1 · 选择服务器</h2>
      <p class="muted" style="margin: 0 0 10px">
        价格按服务器 + 阵营隔离：同一服务器同一阵营的玩家共享彼此导入的拍卖行价格
        （联盟与部落拍卖行分开，选错价格会不准）。切换服务器请慎重。
      </p>
      <div class="flex flex-wrap">
        <select v-model="selectedId" @change="onPickServer" style="min-width: 260px">
          <option :value="0" disabled>— 选择已有服务器 —</option>
          <option v-for="s in servers" :key="s.id" :value="s.id">
            {{ s.name }}（{{ s.batch_count }} 次导入 / {{ s.route_count }} 条路线）
          </option>
        </select>
        <span v-if="currentFaction !== 'both'" class="flex" style="gap: 6px; align-items: center">
          <FactionIcon :faction="currentFaction" :size="20" />
          <span>{{ currentFaction === "alliance" ? "联盟" : "部落" }}服务器，仅见本阵营价格</span>
        </span>
        <div class="flex">
          <input v-model="newName" type="text" placeholder="新服务器名称，如：无限·安苏" style="width: 220px"
            @keyup.enter="onCreate" />
          <button class="btn" @click="onCreate" :disabled="!newName.trim()">＋ 新建</button>
        </div>
      </div>
      <div class="flex flex-wrap" style="margin-top: 10px; gap: 14px; align-items: center">
        <span class="muted">新建服务器阵营：</span>
        <label v-for="f in factionOptions" :key="f.value" class="faction-opt"
               :class="{ active: newFaction === f.value }">
          <input type="radio" :value="f.value" v-model="newFaction" />
          <FactionIcon :faction="f.value" :size="22" />
          <span>{{ f.label }}</span>
        </label>
        <span class="muted" style="font-size: 12px">不确定或单阵营服可选「双阵营共用」</span>
      </div>
    </section>

    <section class="panel">
      <h2>2 · 选择专业</h2>
      <div v-if="professions.length" class="prof-grid">
      <div v-for="p in professions" :key="p.key" class="prof-card" @click="onPickProf(p)">
        <div class="icon">
          <ItemIcon :icon="p.icon" :name="p.name" :size="36" />
        </div>
        <div class="name">{{ p.name }}</div>
        <div class="count">{{ p.recipe_count }} 个配方</div>
      </div>
      </div>
      <div v-else class="empty">专业数据加载中…</div>
    </section>

    <section class="panel" v-if="session.state.professionKey">
      <h2>下一步</h2>
      <div class="flex flex-wrap">
        <RouterLink class="btn primary" to="/plan">进入冲级计划 →</RouterLink>
        <RouterLink class="btn" to="/import">先导入 AUC 价格 →</RouterLink>
        <RouterLink class="btn" to="/routes">看看别人分享的路线 →</RouterLink>
      </div>
    </section>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, ref } from "vue";
import { RouterLink, useRouter } from "vue-router";
import { api } from "@/api/client";
import FactionIcon from "@/components/FactionIcon.vue";
import ItemIcon from "@/components/ItemIcon.vue";
import { useSessionStore } from "@/stores/session";
import type { Faction, Profession, Server } from "@/types";

const session = useSessionStore();
const router = useRouter();
const servers = ref<Server[]>([]);
const professions = ref<Profession[]>([]);
const selectedId = ref(0);
const newName = ref("");
const newFaction = ref<Faction>("both");

const factionOptions: { value: Faction; label: string }[] = [
  { value: "alliance", label: "联盟" },
  { value: "horde", label: "部落" },
  { value: "both", label: "双阵营共用" },
];

const currentFaction = computed<Faction>(() => {
  const s = servers.value.find((x) => x.id === selectedId.value);
  return (s?.faction as Faction) ?? "both";
});

onMounted(async () => {
  servers.value = await api.listServers();
  professions.value = await api.listProfessions();
  selectedId.value = session.state.serverId ?? 0;
});

function onPickServer() {
  const s = servers.value.find((x) => x.id === selectedId.value);
  if (s) session.setServer(s.id, s.name, (s.faction as Faction) ?? "both");
}

async function onCreate() {
  const name = newName.value.trim();
  if (!name) return;
  const s = await api.createServer(name, newFaction.value);
  servers.value = await api.listServers();
  selectedId.value = s.id;
  session.setServer(s.id, s.name, (s.faction as Faction) ?? newFaction.value);
  newName.value = "";
}

function onPickProf(p: Profession) {
  if (!session.state.serverId) {
    alert("请先选择或新建服务器");
    return;
  }
  session.setProfession(p.key);
  router.push("/plan");
}
</script>

<style scoped>
.faction-opt {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  padding: 4px 10px;
  border: 1px solid var(--border, #d8d3c4);
  border-radius: 6px;
  cursor: pointer;
}
.faction-opt.active {
  border-color: #b08b3e;
  background: rgba(176, 139, 62, 0.12);
}
.faction-opt input {
  accent-color: #b08b3e;
}
</style>
