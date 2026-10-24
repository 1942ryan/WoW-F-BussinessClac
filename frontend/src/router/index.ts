import { createRouter, createWebHistory } from "vue-router";

const router = createRouter({
  history: createWebHistory(),
  routes: [
    { path: "/", name: "home", component: () => import("@/views/HomeView.vue") },
    { path: "/import", name: "import", component: () => import("@/views/ImportView.vue") },
    { path: "/plan", name: "plan", component: () => import("@/views/PlanView.vue") },
    { path: "/routes", name: "routes", component: () => import("@/views/RoutesView.vue") },
  ],
});

export default router;
