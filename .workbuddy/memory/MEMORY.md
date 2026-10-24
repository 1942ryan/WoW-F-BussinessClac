# WoW-F-BussinessClac 长期约定

- 仓库：https://github.com/1942ryan/WoW-F-BussinessClac.git（main）
- 本地：后端 venv `C:/Users/1942r/.workbuddy/binaries/python/envs/wowfc/Scripts/python.exe`，跑 `uvicorn app.main:app --port 8787`；前端 `frontend/`（node 在 `C:/Users/1942r/.workbuddy/binaries/node/versions/22.22.2-6/`），构建产物复制到 `backend/static/`
- 涨点几率：默认「客户端公式」=(灰档-当前)/(灰档-黄档)，橙档 100%（WowWiki 存档 + SkillUpProbability 插件实证）；界面可切 fixed 固定档位（默认 100/50/25，env WOWFC_PROB_* 或请求参数）
- NPC 限量材料：`Item.type == "Herb"` 即判定限量（地根草/跌打草/皇血草等），只走拍卖行价；手工追加改 `calc.py` 的 `MANUAL_LIMITED_ITEM_IDS`
- 配方产物处置：全局默认 + `recipe_dispositions` 逐配方覆盖；确认配方有 `confirmed_counts`（默认 1 次，用尽退出路线）
- 专业图标：`seed.py` 的 PROFESSION_ICONS 映射（官方 CDN /tubiao/）；金钱是前端 Money.vue 的 SVG 硬币图标
- 页面布局：PlanView 左右两栏（左参数/右结果优先），sticky 侧栏
- 测试：`cd backend && pytest tests/ -q`（57 个）
