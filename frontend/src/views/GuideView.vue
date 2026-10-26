<template>
  <section class="panel">
    <h2>导价教程 · 把本站模板送进游戏，再把价格导回来</h2>
    <p class="muted" style="margin-top: 0; line-height: 1.7">
      本站不抓拍卖行数据（私服没有公开接口），价格靠玩家自己从游戏里导一次。
      流程一共 5 步：<b>本站出清单 → 游戏内 AUC 导入清单 → 扫价 → 导出价格 → 回本站粘贴</b>，
      最后再确认一下价格有效期。全程 3 分钟，一个角色扫一次，全服同阵营玩家都能用。
    </p>

    <div class="flow">
      <span v-for="(s, i) in steps" :key="s.key" class="flow-step">
        <b>{{ i + 1 }}</b>{{ s.nav }}
      </span>
    </div>

    <div class="alert info" style="margin-top: 12px">
      前置条件：装好 <b>AUC</b>（Auctionator 拍卖行助手）插件，角色能打开拍卖行（主城 AH 或远程拍卖机器人）。
      本教程按 AUC 的中文界面写，按钮名以你客户端实际显示为准。
    </div>
  </section>

  <section v-for="(s, i) in steps" :key="s.key" class="panel step">
    <h2>
      <span class="step-no">{{ i + 1 }}</span>{{ s.title }}
      <span class="step-where">{{ s.where }}</span>
    </h2>

    <ul class="acts">
      <li v-for="(a, j) in s.actions" :key="j" v-html="a"></li>
    </ul>

    <figure class="shot">
      <img v-if="!failed[s.key]" :src="s.image" :alt="s.title" @error="failed[s.key] = true" />
      <div v-else class="shot-empty">
        <div class="se-title">📷 待放图：{{ s.image }}</div>
        <div class="se-sub">建议 {{ s.size || '1200×675' }}（16:9）· 截图要点：</div>
        <div class="se-cap">{{ s.capture }}</div>
      </div>
      <figcaption v-if="s.caption">{{ s.caption }}</figcaption>
    </figure>

    <p v-if="s.tip" class="tip">💡 {{ s.tip }}</p>
  </section>

  <section class="panel">
    <h2>需要哪几张图</h2>
    <p class="muted" style="margin-top: 0">
      把下面 6 张图按文件名放进项目的 <code>frontend/public/guide/</code>（构建后会出现在
      <code>/guide/</code> 下），刷新本页就会自动显示；没放图时这里显示的是占位说明。
    </p>
    <table class="grid">
      <thead>
        <tr><th>文件名</th><th>拍什么</th><th>注意</th></tr>
      </thead>
      <tbody>
        <tr v-for="s in steps" :key="'t' + s.key">
          <td><code>{{ s.image }}</code></td>
          <td>{{ s.capture }}</td>
          <td class="muted">{{ s.caption || "—" }}</td>
        </tr>
      </tbody>
    </table>
    <p class="muted" style="margin-bottom: 0">
      尺寸不必严格，宽度 1000–1600px 之间最清晰；截图里别带自己的角色名/公会名，方便公开分享。
    </p>
  </section>
</template>

<script setup lang="ts">
import { reactive } from "vue";

interface Step {
  key: string;
  /** 顶部流程链上的短名 */
  nav: string;
  title: string;
  /** 这一步在哪操作 */
  where: string;
  actions: string[];
  image: string;
  capture: string;
  caption?: string;
  tip?: string;
  size?: string;
}

const failed = reactive<Record<string, boolean>>({});

const steps: Step[] = [
  {
    key: "export",
    nav: "本站出清单",
    title: "在本站生成 AUC 关注清单",
    where: "本站 · 冲级计划 / 价格导入",
    actions: [
      "在「冲级计划」页顶部点 <b>导出模板</b>（或在「价格导入」页点 <b>导出模板（AUC 关注清单）</b>）。",
      "确认专业与技能范围（不填就是整个专业），点 <b>复制文本</b>，或 <b>下载 .txt</b> 存到桌面。",
      "文本形如 <code>工程学^铜锭^弱效助熔剂^结构图：机械松鼠^…</code>：第一段是清单名，后面全是物品名，用 <code>^</code> 分隔。",
    ],
    image: "/guide/step1.png",
    capture: "「导出模板」弹窗：专业下拉、清单名与物品数那一行、复制文本/下载按钮，能看到清单文本预览最好",
    caption: "清单里同时包含材料、成品和设计图 —— 三样都要有价，路线才算得准。",
    tip: "同一个专业只需导一次清单；换了专业或技能范围，重新生成一份即可。",
  },
  {
    key: "import-list",
    nav: "游戏内导入清单",
    title: "把清单粘进游戏的 AUC 购物清单",
    where: "游戏内 · /auc → 购物清单",
    actions: [
      "游戏里输入 <code>/auc</code>（或点小地图旁的 AUC 图标）打开拍卖行助手。",
      "切到 <b>购物清单 / Shopping lists</b> 标签，点 <b>新建清单</b>，名字随意（建议就叫「冲级-工程学」）。",
      "点清单详情里的 <b>导入 / Import</b>，把刚才复制的文本整段粘进去，确认。",
      "列表里应该出现几十上百个物品，每个前面能填需要买的数量 —— 数量留空也没关系，我们只要价格。",
    ],
    image: "/guide/step2.png",
    capture: "AUC 购物清单界面：左边清单名列表、右边导入按钮与物品列表（能看到「铜锭」「弱效助熔剂」这类名字）",
    caption: "AUC 的中文界面里「购物清单」也叫「采购清单 / Shopping list」，不同版本叫法略有差异。",
    tip: "清单导入失败最常见的原因是粘贴时丢了分隔符——整段复制，别手动改中间的 ^。",
  },
  {
    key: "scan",
    nav: "扫价",
    title: "让 AUC 把清单里的价格扫一遍",
    where: "游戏内 · 拍卖行前",
    actions: [
      "人物站到拍卖行 NPC 旁边（或能打开拍卖行的机器人），打开拍卖行界面。",
      "在购物清单页点 <b>搜索全部 / 扫描</b>，等进度条跑完（几十个物品一般 10–30 秒）。",
      "扫完后每一项后面会显示最低价；显示「无」的就是拍卖行当前没货，这种物品本站会按卖店价兜底。",
    ],
    image: "/guide/step3.png",
    capture: "扫完价的购物清单：每行物品后面带价格（金/银/铜），最好能看到几个「无」的对比",
    caption: "扫描用的是当前角色的拍卖行数据 —— 所以联盟号扫的价只对联盟有效，本站价格按「服务器 + 阵营」分开存。",
    tip: "物价波动大时（比如刚开新 CD），隔几小时重扫一次更准。",
  },
  {
    key: "export-price",
    nav: "导出价格",
    title: "从 AUC 导出价格文本",
    where: "游戏内 · 购物清单 → 导出",
    actions: [
      "在清单页点 <b>导出 / Export</b>（有的版本在清单名上右键），选 <b>导出为 CSV / 复制到剪贴板</b>。",
      "导出内容表头是 <code>\"价格\",\"名称\",\"物品等级\",\"拥有？\",\"可售数量\"</code>，价格单位是<b>铜</b>。",
      "能复制就复制；只能存文件就存成 <code>.csv</code> 或 <code>.txt</code>，记住放在哪。",
    ],
    image: "/guide/step4.png",
    capture: "AUC 导出对话框，或导出后打开的 CSV 前几行（要能看清表头和「价格」这一列）",
    caption: "有「物品等级」列很关键：本服存在同名不同物品（如劣质炸药 10 级 / 20 级），靠它区分。",
    tip: "导出的 CSV 可以直接拖到本站导入框，不用手动整理格式。",
  },
  {
    key: "import-back",
    nav: "回本站导入",
    title: "把价格导回本站，自动重算路线",
    where: "本站 · 价格导入 / 冲级计划",
    actions: [
      "回到本站「价格导入」页（或计划页顶部的 <b>价格导入</b> 按钮），把 CSV 文本粘进大框，或选择文件。",
      "填个昵称（可选，方便别人知道这批价是谁导的），点 <b>开始导入</b>。",
      "看到「本次导入：N 行 · 匹配 X · 未匹配 Y · 入库 Z」就成功了；未匹配通常是本服没有这件物品或改了名。",
      "回到「冲级计划」点 <b>计算路线</b>（已算过会自动重算），价格立刻生效。",
    ],
    image: "/guide/step5.png",
    capture: "本站「价格导入」页：粘贴框里是 AUC 导出的 CSV + 导入成功后的绿色统计条",
    caption: "导入的是「一次快照」，不会覆盖历史记录——所以后面还能看到价格变化。",
    tip: "导入后计划页顶部会显示这批价的有效期（默认 24 小时），过期会红字提醒，重新导一次就好。",
  },
  {
    key: "freshness",
    nav: "看有效期",
    title: "确认价格还没过期",
    where: "本站 · 冲级计划顶部",
    actions: [
      "计划页「计算参数」下面有一行 <b>价格数据</b>：显示最近一次导入是多久前、覆盖多少个物品。",
      "超过 <b>24 小时</b>有效期会变成红字，并告诉你其中多少个物品的报价已过期。",
      "悬停任意物品图标或<b>物品名字</b>，物品卡里也会写明这条拍卖价是多久前导的。",
    ],
    image: "/guide/step6.png",
    capture: "计划页顶部「价格数据 · 最近一次导入 X 小时前（有效期 24 小时）」那一行 + 一个物品悬停卡",
    caption: "价格旧了不用慌：老价格仍会参与计算，只是提醒你自己判断要不要重扫。",
    tip: "看到红字就顺手扫一遍再导回来，路线误差通常能压到几个百分点以内。",
    size: "1200×675",
  },
];
</script>

<style scoped>
.flow {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  margin-top: 10px;
}
.flow-step {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  padding: 4px 10px;
  border-radius: 999px;
  background: rgba(176, 139, 62, 0.12);
  border: 1px solid rgba(176, 139, 62, 0.35);
  font-size: 12.5px;
  color: #7a5c00;
}
.flow-step b {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 17px;
  height: 17px;
  border-radius: 50%;
  background: #b08b3e;
  color: #fff;
  font-size: 11px;
}
.step-no {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 22px;
  height: 22px;
  margin-right: 8px;
  border-radius: 50%;
  background: #b08b3e;
  color: #fff;
  font-size: 13px;
  vertical-align: 2px;
}
.step-where {
  margin-left: 8px;
  font-size: 12px;
  font-weight: 400;
  color: var(--muted, #7a7264);
}
.acts {
  margin: 10px 0 0;
  padding-left: 22px;
  font-size: 13px;
  line-height: 1.85;
}
.acts code {
  padding: 1px 4px;
  border-radius: 3px;
  background: rgba(128, 128, 128, 0.14);
  font-size: 12px;
}
.shot {
  margin: 12px 0 0;
}
.shot img {
  display: block;
  width: 100%;
  max-width: 900px;
  border: 1px solid var(--border, #d8d3c4);
  border-radius: 6px;
}
/* 没放图时的占位：写清楚要拍什么，作者照着一格一格补图就行 */
.shot-empty {
  max-width: 900px;
  padding: 18px 16px;
  border: 1px dashed rgba(176, 139, 62, 0.6);
  border-radius: 6px;
  background: rgba(176, 139, 62, 0.06);
}
.se-title {
  font-weight: 600;
  color: #8a6100;
  font-size: 13px;
}
.se-sub {
  margin-top: 6px;
  font-size: 12px;
  color: var(--muted, #7a7264);
}
.se-cap {
  margin-top: 4px;
  font-size: 13px;
  line-height: 1.6;
}
.shot figcaption {
  margin-top: 6px;
  font-size: 12px;
  color: var(--muted, #7a7264);
  line-height: 1.6;
}
.tip {
  margin: 10px 0 0;
  padding: 7px 10px;
  border-radius: 6px;
  background: rgba(76, 132, 76, 0.09);
  font-size: 12.5px;
  line-height: 1.6;
  color: #3f6b3f;
}
</style>
