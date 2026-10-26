import { createRouter, createWebHistory } from "vue-router";

const router = createRouter({
  history: createWebHistory(),
  routes: [
    { path: "/", name: "home", component: () => import("@/views/HomeView.vue") },
    { path: "/import", name: "import", component: () => import("@/views/ImportView.vue") },
    { path: "/plan", name: "plan", component: () => import("@/views/PlanView.vue") },
    { path: "/routes", name: "routes", component: () => import("@/views/RoutesView.vue") },
    // 导价教程：图文步骤，教玩家把模板导进游戏 AUC 再导回价格
    { path: "/guide", name: "guide", component: () => import("@/views/GuideView.vue") },
    // 分享链接落地页：/r/{share_code} 直接打开一条已保存的路线
    { path: "/r/:code", name: "route-share", component: () => import("@/views/RouteShareView.vue") },
  ],
});

export default router;
