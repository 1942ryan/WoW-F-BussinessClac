<script setup lang="ts">
/**
 * 物品详情 tooltip（悬停物品图标弹出，仿 wowhead 数据库样式）。
 * 数据懒加载：悬停 250ms 后请求 GET /items/{id}?server_id=，结果按物品缓存。
 */
import { computed, onBeforeUnmount, ref, watch } from "vue";
import { api } from "@/api/client";
import Money from "./Money.vue";
import ItemIcon from "./ItemIcon.vue";
import { useSessionStore } from "@/stores/session";
import type { ItemDetail } from "@/types";

const props = withDefaults(
  defineProps<{
    itemId: number | null;
    /** tooltip 是否可见（由父级 hover 控制） */
    visible: boolean;
    /** 锚点元素（用于定位） */
    anchor?: HTMLElement | null;
    size?: number;
  }>(),
  { itemId: null, visible: false, anchor: null, size: 24 }
);

const emit = defineEmits<{ (e: "keep"): void; (e: "leave"): void }>();

const session = useSessionStore();
const detail = ref<ItemDetail | null>(null);
const loading = ref(false);
const pos = ref({ left: 0, top: 0 });
let timer: number | undefined;
let reqSeq = 0;

/** 物品详情缓存（会话内有效，避免重复请求） */
const cache = new Map<number, ItemDetail>();

const QUALITY_COLORS: Record<number, string> = {
  0: "#9d9d9d", // 粗糙
  1: "#ffffff", // 普通
  2: "#1eff00", // 优秀
  3: "#0070dd", // 精良
  4: "#a335ee", // 史诗
  5: "#ff8000", // 传说
};

const TYPE_CN: Record<string, string> = {
  Herb: "草药",
  "Metal & Stone": "金属与矿石",
  Leather: "皮革",
  Cloth: "布料",
  Meat: "肉类",
  Elemental: "元素",
  Potion: "药剂",
  Elixir: "药水",
  Flask: "合剂",
  Reagent: "材料",
  Gem: "宝石",
  "Trade Goods": "商品",
  Food: "食物",
  Drink: "饮料",
  "Parts": "零件",
  Explosive: "爆炸物",
  Device: "装置",
  Weapon: "武器",
  Enchanting: "附魔",
  Bag: "容器",
};

const nameStyle = computed(() => ({
  color: QUALITY_COLORS[detail.value?.quality ?? 0] ?? "#ffffff",
}));

const typeLabel = computed(() => {
  const t = detail.value?.type;
  if (!t) return null;
  return TYPE_CN[t] ?? t;
});

function place() {
  const el = props.anchor;
  if (!el) return;
  const r = el.getBoundingClientRect();
  const w = 300;
  const h = 190;
  let left = r.right + 10;
  if (left + w > window.innerWidth - 8) left = Math.max(8, r.left - w - 10);
  let top = r.top - 8;
  if (top + h > window.innerHeight - 8) top = Math.max(8, window.innerHeight - h - 8);
  pos.value = { left, top };
}

async function load() {
  if (props.itemId == null) return;
  const cached = cache.get(props.itemId);
  if (cached) {
    detail.value = cached;
    return;
  }
  loading.value = true;
  const seq = ++reqSeq;
  try {
    const d = await api.itemDetail(props.itemId, session.state.serverId ?? undefined);
    if (seq === reqSeq) {
      cache.set(props.itemId, d);
      detail.value = d;
    }
  } catch {
    if (seq === reqSeq) detail.value = null;
  } finally {
    if (seq === reqSeq) loading.value = false;
  }
}

watch(
  () => props.visible,
  (v) => {
    window.clearTimeout(timer);
    if (v) {
      timer = window.setTimeout(() => {
        place();
        void load();
      }, 250);
    } else {
      detail.value = null;
      loading.value = false;
    }
  }
);

onBeforeUnmount(() => window.clearTimeout(timer));
</script>

<template>
  <Teleport to="body">
    <div
      v-if="visible"
      class="item-tip"
      :style="{ left: pos.left + 'px', top: pos.top + 'px' }"
      @mouseenter="$emit('keep')"
      @mouseleave="$emit('leave')"
    >
      <div class="tip-head">
        <ItemIcon :icon="detail?.icon" :name="detail?.name ?? ''" :size="36" />
        <div class="tip-title">
          <div class="tip-name" :style="nameStyle">{{ detail?.name ?? "…" }}</div>
          <div v-if="detail?.item_level" class="tip-sub">物品等级：{{ detail.item_level }}</div>
        </div>
      </div>
      <div v-if="loading" class="tip-loading">加载中…</div>
      <template v-else-if="detail">
        <div v-if="typeLabel" class="tip-row muted">类型：{{ typeLabel }}</div>
        <div class="tip-row">
          <span class="muted">售价：</span>
          <Money :value="detail.vendor_price" :size="12" />
        </div>
        <div class="tip-row">
          <span class="muted">拍卖行：</span>
          <Money v-if="detail.effective_ah !== null" :value="detail.effective_ah" :size="12" />
          <span v-else class="muted">暂无价格</span>
        </div>
        <div v-if="detail.record_count" class="tip-row muted">
          价格流水 {{ detail.record_count }} 条
        </div>
      </template>
    </div>
  </Teleport>
</template>

<style scoped>
.item-tip {
  position: fixed;
  z-index: 200;
  width: 300px;
  padding: 10px 12px;
  background: rgba(18, 16, 12, 0.96);
  border: 1px solid #6b5a35;
  border-radius: 6px;
  box-shadow: 0 6px 24px rgba(0, 0, 0, 0.55);
  color: #e8e2d0;
  font-size: 12.5px;
  line-height: 1.6;
  pointer-events: auto;
}
.tip-head {
  display: flex;
  gap: 10px;
  align-items: flex-start;
  margin-bottom: 6px;
}
.tip-title {
  min-width: 0;
}
.tip-name {
  font-size: 14px;
  font-weight: 700;
  word-break: break-all;
}
.tip-sub {
  color: #b8ae94;
  font-size: 12px;
}
.tip-row {
  display: flex;
  align-items: center;
  gap: 4px;
}
.tip-loading {
  color: #b8ae94;
}
.muted {
  color: #b8ae94;
}
</style>
