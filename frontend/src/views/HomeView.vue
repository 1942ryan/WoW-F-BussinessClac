<template>
  <div>
    <section class="panel">
      <h2>1 · 选择服务器</h2>
      <p class="muted" style="margin: 0 0 10px">
        价格按服务器隔离：同一服务器下的玩家共享彼此导入的拍卖行价格。选错服价格会不准，切换服务器请慎重。
      </p>
      <div class="flex flex-wrap">
        <select v-model="selectedId" @change="onPickServer" style="min-width: 220px">
          <option :value="0" disabled>— 选择已有服务器 —</option>
          <option v-for="s in servers" :key="s.id" :value="s.id">
            {{ s.name }}（{{ s.batch_count }} 次导入 / {{ s.route_count }} 条路线）
          </option>
        </select>
        <div class="flex">
          <input v-model="newName" type="text" placeholder="新服务器名称，如：无限·安苏" style="width: 220px"
            @keyup.enter="onCreate" />
          <button class="btn" @click="onCreate" :disabled="!newName.trim()">＋ 新建</button>
        </div>
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
import { onMounted, ref } from "vue";
import { RouterLink, useRouter } from "vue-router";
import { api } from "@/api/client";
import ItemIcon from "@/components/ItemIcon.vue";
import { useSessionStore } from "@/stores/session";
import type { Profession, Server } from "@/types";

const session = useSessionStore();
const router = useRouter();
const servers = ref<Server[]>([]);
const professions = ref<Profession[]>([]);
const selectedId = ref(0);
const newName = ref("");

onMounted(async () => {
  servers.value = await api.listServers();
  professions.value = await api.listProfessions();
  selectedId.value = session.state.serverId ?? 0;
});

function onPickServer() {
  const s = servers.value.find((x) => x.id === selectedId.value);
  if (s) session.setServer(s.id, s.name);
}

async function onCreate() {
  const name = newName.value.trim();
  if (!name) return;
  const s = await api.createServer(name);
  servers.value = await api.listServers();
  selectedId.value = s.id;
  session.setServer(s.id, s.name);
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
