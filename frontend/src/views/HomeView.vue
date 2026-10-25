<template>
  <div>
    <section class="panel">
      <h2>1 · 选择服务器</h2>
      <p class="muted" style="margin: 0 0 10px">
        服务器为 <b>PVP / PVE / RP</b> 三个。联盟与部落的拍卖行<b>不互通</b>，
        价格按「服务器 + 阵营」隔离存储，选错阵营价格会不准。
      </p>

      <div class="pick-row">
        <span class="pick-label">服务器</span>
        <button v-for="s in SERVER_PRESETS" :key="s" class="btn pick"
                :class="{ active: pickedServer === s }" @click="pickedServer = s">
          {{ s }}
        </button>
      </div>

      <div class="pick-row">
        <span class="pick-label">阵营</span>
        <button v-for="f in FACTIONS" :key="f.value" class="btn pick faction"
                :class="{ active: pickedFaction === f.value }" @click="pickedFaction = f.value">
          <FactionIcon :faction="f.value" :size="20" />
          <span>{{ f.label }}</span>
        </button>
      </div>

      <div class="pick-row" style="margin-top: 12px">
        <span class="pick-label"></span>
        <button class="btn primary" :disabled="!pickedServer || busy" @click="onEnter">
          {{ enterLabel }}
        </button>
        <RouterLink v-if="session.state.serverId" class="btn primary" to="/plan">下一步：选择专业 →</RouterLink>
        <span v-if="status" class="muted status">{{ status }}</span>
      </div>

      <!-- 旧服务器（非 PVP/PVE/RP 组合名，历史价格仍可用） -->
      <details v-if="legacyServers.length" class="legacy">
        <summary class="muted">旧服务器 / 历史数据（{{ legacyServers.length }}）</summary>
        <div class="flex flex-wrap" style="margin-top: 8px">
          <button v-for="s in legacyServers" :key="s.id" class="btn small" @click="onPickLegacy(s)"
                  :class="{ active: session.state.serverId === s.id }">
            {{ s.name }}（{{ s.batch_count }} 次导入 / {{ s.route_count }} 条路线）
            <FactionIcon v-if="s.faction && s.faction !== 'both'" :faction="s.faction" :size="14" />
          </button>
        </div>
      </details>
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

/** 服务器名单固定为 PVP / PVE / RP 三个 */
const SERVER_PRESETS = ["PVP", "PVE", "RP"];
/** 阵营只有联盟与部落（中立拍卖行不参与价格隔离，已下线） */
const FACTIONS: { value: Faction; label: string }[] = [
  { value: "alliance", label: "联盟" },
  { value: "horde", label: "部落" },
];

const pickedServer = ref("");
const pickedFaction = ref<Faction>("alliance");
const busy = ref(false);
const status = ref("");

/** 服务器 + 阵营 = 唯一服务器名（后端 name 唯一，天然支持六个组合） */
const comboName = computed(() => {
  if (!pickedServer.value) return "";
  const suffix = pickedFaction.value === "alliance" ? "联盟" : "部落";
  return `${pickedServer.value}·${suffix}`;
});

const existing = computed(
  () => servers.value.find((s) => s.name === comboName.value) ?? null
);

const enterLabel = computed(() => {
  if (!pickedServer.value) return "先选服务器和阵营";
  return existing.value ? `使用 ${comboName.value}` : `创建 ${comboName.value}`;
});

/** 名字不属于预设组合的服务器（保留历史价格数据） */
const legacyServers = computed(() =>
  servers.value.filter((s) => !SERVER_PRESETS.some((p) => s.name.startsWith(`${p}·`)))
);

onMounted(async () => {
  servers.value = await api.listServers();
  professions.value = await api.listProfessions();
  // 从当前会话反解析「服务器·阵营」
  const cur = servers.value.find((s) => s.id === session.state.serverId);
  if (cur) {
    const [p, f] = cur.name.split("·");
    if (SERVER_PRESETS.includes(p) && (f === "联盟" || f === "部落")) {
      pickedServer.value = p;
      pickedFaction.value = f === "联盟" ? "alliance" : "horde";
    }
  }
});

async function onEnter() {
  if (!pickedServer.value) return;
  busy.value = true;
  try {
    let target = existing.value;
    if (!target) {
      const created = await api.createServer(comboName.value, pickedFaction.value);
      servers.value = await api.listServers();
      target = servers.value.find((s) => s.id === created.id) ?? null;
      status.value = created.existed ? `已切换到 ${comboName.value}` : `已创建 ${comboName.value}`;
    } else {
      status.value = `已切换到 ${comboName.value}`;
    }
    if (target) {
      session.setServer(target.id, target.name, (target.faction as Faction) ?? pickedFaction.value);
    }
  } finally {
    busy.value = false;
  }
}

function onPickLegacy(s: Server) {
  session.setServer(s.id, s.name, (s.faction as Faction) ?? "both");
  status.value = `已切到旧服务器「${s.name}」，历史价格仍在`;
}

function onPickProf(p: Profession) {
  if (!session.state.serverId) {
    alert("请先选择服务器");
    return;
  }
  session.setProfession(p.key);
  router.push("/plan");
}
</script>

<style scoped>
.pick-row {
  display: flex;
  flex-wrap: wrap;
  gap: 10px;
  align-items: center;
  margin-bottom: 10px;
}
.pick-label {
  width: 52px;
  flex: none;
  color: var(--muted);
  font-size: 13px;
}
.pick {
  min-width: 92px;
  padding: 6px 14px;
}
.pick.faction {
  display: inline-flex;
  align-items: center;
  gap: 6px;
}
.pick.active {
  background: var(--gold-soft, rgba(176, 139, 62, 0.16));
  border-color: #b08b3e;
  color: #7a5c00;
  font-weight: 600;
}
.status {
  font-size: 12px;
}
.legacy {
  margin-top: 12px;
  border-top: 1px solid var(--border, #d8d3c4);
  padding-top: 10px;
}
.legacy summary {
  cursor: pointer;
  font-size: 13px;
}
</style>
