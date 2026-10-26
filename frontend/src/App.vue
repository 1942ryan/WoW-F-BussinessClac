<template>
  <header class="topbar">
    <span class="brand">⚒ 制造业冲级价格计算器</span>
    <nav>
      <RouterLink to="/">首页 · 选专业</RouterLink>
      <RouterLink to="/plan">冲级计划</RouterLink>
      <RouterLink to="/import">价格导入</RouterLink>
      <RouterLink to="/guide">导价教程</RouterLink>
      <RouterLink to="/routes">路线分享</RouterLink>
    </nav>
    <span v-if="session.state.serverName" class="server-chip">🖥 {{ session.state.serverName }}</span>
  </header>
  <main class="main">
    <RouterView />
  </main>
</template>

<script setup lang="ts">
import { useSessionStore } from "@/stores/session";

const session = useSessionStore();
</script>
