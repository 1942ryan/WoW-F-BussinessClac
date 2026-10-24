# WoW-F-BussinessClac 长期约定

- 仓库：https://github.com/1942ryan/WoW-F-BussinessClac.git（main）
- 本地：后端 venv `C:/Users/1942r/.workbuddy/binaries/python/envs/wowfc/Scripts/python.exe`，跑 `uvicorn app.main:app --port 8787`；前端 `frontend/`（node 在 `C:/Users/1942r/.workbuddy/binaries/node/versions/22.22.2-6/`），构建产物复制到 `backend/static/`
- 涨点几率：默认「客户端公式」=(灰档-当前)/(灰档-黄档)，橙档 100%（WowWiki 存档 + SkillUpProbability 插件实证）；界面可切 fixed 固定档位（默认 100/50/25，env WOWFC_PROB_* 或请求参数）
- NPC 限量材料：`Item.type == "Herb"` 即判定限量（地根草/跌打草/皇血草等），只走拍卖行价；手工追加改 `calc.py` 的 `MANUAL_LIMITED_ITEM_IDS`
- 配方产物处置：只有 卖店/拍卖行 两种（自用已下线）；全局固定卖拍卖行 + `recipe_dispositions` 逐配方覆盖
- **确认采用语义**：= 当前技能下可用配方的**优先权** + 次数**上限**（不是目标，绝不多做）；用完退出路线。
  填次数不变结果的常见原因：配方本来就会被选中（上限没触发）/ 当前技能段不可用（未解锁或已变灰）。
  默认 1 次 → 多数配方确认后只做 1 次。测试见 test_calc.py 的 confirmed 系列
- 页面布局（v3）：计算参数置顶全宽 → `.plan-body` grid 3fr/1fr（左配方列表 / 右计算结果 sticky）；
  材料清单 = 右侧滑出抽屉（默认折叠）；`.main` 无 max-width 占满页面
- 成本列负数 = 赚钱：Money.vue `negAsEarn` prop → 红色「赚」前缀 + 绝对值（不显示负号）
- 已固化的计算规则（UI 不再暴露，后端默认值）：涨点=客户端公式、成品默认卖拍卖行、设计图按拍卖行价计入、含设计图配方
- 测试：`cd backend && pytest tests/ -q`（60 个）

## 第二轮迭代（2026-10-24 深夜，commit 8f60511）
- 阵营隔离：`Server.faction` + `PriceRecord.faction`（alliance/horde/both）；both 旧数据作公共底价对阵营服可见；
  effective_prices / prices router 全部带阵营过滤。首页建服带阵营图标单选（FactionIcon：联盟=inv_bannerpvp_02 蓝狮、部落=inv_bannerpvp_01 红龙）
- 同产品步骤合并：calc.py 合并条件去掉 band 相同 → 相邻同 recipe_id 全合并，档位显示 prob→prob_end 区间
- tooltip：GET /items/{id}?server_id=（ItemDetailOut）；ItemIcon 传 itemId 即启用悬停（250ms 防抖 + 模块级缓存），ItemTooltip.vue 仿 wowhead 深色卡
- 采购清单导出：ShoppingExportDialog.vue（前端从 result.materials 生成 `专业采购清单^材料^…`）
- 处置双价格按钮：RecipeOut 加 product_npc_price/product_ah_price；配方行「卖店价/拍卖行价」按钮点价即选中，ghost ↺ 清除覆盖
- 术语统一：AH购买→拍卖行；NPC限量标签全下线（is_limited_vendor 逻辑保留在计价层）
- UI 折行：table.grid.nowrap + .wrap 例外列；配方表 sticky thead + max-height 560；RoutesView 采用按钮移到结果顶部
- 货币图标：官方库 inv_misc_coin_01(金)/02(银)/05(铜)

## 第三轮迭代（2026-10-25，UI 精简 + 确认采用语义澄清）
- 下线固定选项：涨点几率模式/全局成品处置/图纸成本/含设计图配方（固化为后端默认值，前端不发送）
- session store 瘦身 + LS_KEY 升 v2；types.ts Disposition 只留 sell_ah/sell_npc（后端 Literal 保留 self_use 兼容旧存档，
  applyParams 清洗旧覆盖）
- PlanView 重写：参数置顶；左 3/4 配方列表（生产成本/产物处置/技能档/来源/实际成本最右，无收入列）；
  右 1/4 结果（总制作次数+花费；步骤表图纸成本折进制作格）；材料清单右侧抽屉、无来源列
- tooltip 定位为「真实数据卡」：全部取自自有 API，不依赖 wowhead 外部调取
