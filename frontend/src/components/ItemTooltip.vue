<script setup lang="ts">
/**
 * 物品详情 tooltip（悬停物品图标弹出）——版式对齐「游戏内物品信息」：
 *
 *   名称（品质色）  物品等级 N · 物品 ID
 *   ─────────────────────────────
 *   拾取后绑定 / 装备后绑定
 *   胸部            皮甲
 *   护甲值 62
 *   +2 耐力
 *   需要等级 7
 *   装备：xxx（绿色）
 *   售价：1金92铜   ← 带金币/银币/铜币图标
 *
 * 数据来自后端 ItemDetail.tooltip（官方 API 的 tooltip 字段逐行原文），
 * 不是我们拼的：换行、左右分栏（\t）、数值、装备特效全部照搬游戏文本。
 * 悬停 250ms 后按物品 ID 懒加载，会话内缓存。
 */
import { computed, nextTick, onBeforeUnmount, ref, watch } from "vue";
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
const boxEl = ref<HTMLElement | null>(null);
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
  Parts: "零件",
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

/** 一行 tooltip：单列文本，或「部位 | 护甲类型」这类左右两列 */
interface TipRow {
  key: string;
  cls: string;
  text?: string;
  left?: string;
  right?: string;
  money?: number;
}

/** "1金87银58铜" / "1金92铜" / "5铜" → 铜数 */
function parseCopper(text: string): number | null {
  const re = /(\d+)\s*(金|银|铜)/g;
  let total = 0;
  let hit = false;
  let m: RegExpExecArray | null;
  while ((m = re.exec(text)) !== null) {
    hit = true;
    const unit = m[2] === "金" ? 10000 : m[2] === "银" ? 100 : 1;
    total += Number(m[1]) * unit;
  }
  return hit ? total : null;
}

/** 装备特效类文案（游戏里是绿色） */
const GREEN_RE = /^(装备|使用|击中时可能|击中后可能|近战|远程|唯一|装备唯一)[：:]/;
/** 绑定/限制类文案 */
const BIND_RE = /^(拾取后绑定|装备后绑定|已绑定|账号绑定|唯一|唯一装备|需要)/;

const rows = computed<TipRow[]>(() => {
  const lines = detail.value?.tooltip ?? [];
  return lines.map((raw, i) => {
    const key = `r${i}`;
    if (raw.startsWith("售价")) {
      return { key, cls: "price", money: parseCopper(raw) ?? undefined, text: "售价：" };
    }
    const tab = raw.indexOf("\t");
    if (tab > 0) {
      // 官方 text 用 \t 表示左右两栏（胸部 → 皮甲）
      return { key, cls: "two", left: raw.slice(0, tab), right: raw.slice(tab + 1) };
    }
    const line = raw.replace(/^\t+/, ""); // 行首 \t 只是缩进标记（如「药水」）
    let cls = "plain";
    if (rowIsGreen(line)) cls = "green";
    else if (line.startsWith("套装")) cls = "set";
    else if (BIND_RE.test(line)) cls = "bind";
    return { key, cls, text: line };
  });
});

function rowIsGreen(line: string): boolean {
  return GREEN_RE.test(line) && !line.startsWith("唯一");
}

function place() {
  const el = props.anchor;
  if (!el) return;
  const r = el.getBoundingClientRect();
  const w = 320;
  const h = boxEl.value?.offsetHeight ?? 200;
  let left = r.right + 10;
  if (left + w > window.innerWidth - 8) left = Math.max(8, r.left - w - 10);
  // 默认与图标顶部对齐；底部放不下就上移，仍放不下则贴顶
  let top = r.top - 8;
  if (top + h > window.innerHeight - 8) top = Math.max(8, window.innerHeight - h - 8);
  pos.value = { left, top };
}

async function load() {
  if (props.itemId == null) return;
  const cached = cache.get(props.itemId);
  if (cached) {
    detail.value = cached;
    await nextTick();
    place();
    return;
  }
  loading.value = true;
  const seq = ++reqSeq;
  try {
    const d = await api.itemDetail(props.itemId, session.state.serverId ?? undefined);
    if (seq === reqSeq) {
      cache.set(props.itemId, d);
      detail.value = d;
      await nextTick();
      place();
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
      ref="boxEl"
      class="item-tip"
      :style="{ left: pos.left + 'px', top: pos.top + 'px' }"
      @mouseenter="$emit('keep')"
      @mouseleave="$emit('leave')"
    >
      <div class="tip-head">
        <ItemIcon :icon="detail?.icon" :name="detail?.name ?? ''" :size="40" :item-id="null" />
        <div class="tip-title">
          <div class="tip-name" :style="nameStyle">{{ detail?.name ?? "…" }}</div>
          <div class="tip-meta">
            <span v-if="detail?.item_level" class="ilvl">物品等级 {{ detail.item_level }}</span>
            <span v-if="detail" class="item-id">· 物品 {{ detail.item_id }}</span>
          </div>
        </div>
      </div>

      <div v-if="loading" class="tip-loading">加载中…</div>

      <template v-else-if="detail">
        <!-- 游戏内原文：绑定/部位/护甲/属性/需要等级/装备特效/售价 -->
        <div v-if="rows.length" class="tip-body">
          <div v-for="row in rows" :key="row.key" class="tip-line" :class="row.cls">
            <template v-if="row.cls === 'two'">
              <span>{{ row.left }}</span><span class="right">{{ row.right }}</span>
            </template>
            <template v-else-if="row.cls === 'price'">
              <span>{{ row.text }}</span>
              <Money v-if="row.money !== undefined" :value="row.money" :size="12" />
            </template>
            <template v-else>{{ row.text }}</template>
          </div>
        </div>
        <!-- 没有原文数据时退回基础字段，保证不空白 -->
        <div v-else class="tip-body">
          <div v-if="typeLabel" class="tip-line plain">{{ typeLabel }}</div>
          <div class="tip-line price">
            <span>售价：</span>
            <Money :value="detail.vendor_price" :size="12" />
          </div>
        </div>

        <!-- 本站补充：拍卖行参考价（游戏里看不到，冲级要用） -->
        <div class="tip-ah">
          <span class="k">拍卖行</span>
          <Money v-if="detail.effective_ah !== null" :value="detail.effective_ah" :size="12" />
          <span v-else class="none">暂无价格</span>
          <span v-if="detail.record_count" class="cnt">· {{ detail.record_count }} 条流水</span>
        </div>
      </template>
    </div>
  </Teleport>
</template>

<style scoped>
/* 深色石质面板，贴近游戏内物品信息框 */
.item-tip {
  position: fixed;
  z-index: 200;
  width: 320px;
  max-width: calc(100vw - 16px);
  max-height: 70vh;
  overflow-y: auto;
  padding: 10px 12px 8px;
  background: linear-gradient(180deg, #14110c 0%, #0d0b08 100%);
  border: 1px solid #6b5a35;
  border-radius: 6px;
  box-shadow: 0 8px 28px rgba(0, 0, 0, 0.6);
  color: #f2efe8;
  font-size: 12.5px;
  line-height: 1.55;
  pointer-events: auto;
}
.tip-head {
  display: flex;
  gap: 10px;
  align-items: flex-start;
  border-bottom: 1px solid rgba(255, 255, 255, 0.08);
  padding-bottom: 7px;
  margin-bottom: 6px;
}
.tip-title {
  min-width: 0;
}
.tip-name {
  font-size: 14.5px;
  font-weight: 700;
  line-height: 1.35;
  word-break: break-all;
}
.tip-meta {
  display: flex;
  gap: 4px;
  font-size: 11.5px;
  color: #b8ae94;
}
.ilvl {
  color: #f0d264;
}
.item-id {
  color: #8d8571;
}
.tip-body {
  display: flex;
  flex-direction: column;
}
.tip-line {
  white-space: pre-wrap;
  word-break: break-word;
}
/* 左右两栏（部位 / 护甲类型） */
.tip-line.two {
  display: flex;
  justify-content: space-between;
  gap: 14px;
}
.tip-line.two .right {
  text-align: right;
  flex: none;
}
/* 装备/使用特效 —— 游戏内是绿色 */
.tip-line.green {
  color: #1eff00;
}
.tip-line.set {
  color: #ffd100;
}
.tip-line.bind,
.tip-line.plain {
  color: #ffffff;
}
.tip-line.price {
  display: flex;
  align-items: center;
  gap: 4px;
  margin-top: 4px;
  color: #ffffff;
}
.tip-loading {
  color: #b8ae94;
}
.tip-ah {
  display: flex;
  align-items: center;
  gap: 5px;
  margin-top: 7px;
  padding-top: 6px;
  border-top: 1px dashed rgba(255, 255, 255, 0.12);
  font-size: 12px;
  color: #cfc6ad;
}
.tip-ah .k {
  color: #c2a86a;
}
.tip-ah .none,
.tip-ah .cnt {
  color: #8d8571;
}
</style>
