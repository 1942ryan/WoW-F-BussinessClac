# WoW-F-BussinessClac · 魔兽世界无限 · 制造业冲级价格计算器

基于《魔兽世界：无限》版本配方数据的在线冲级规划工具：导入游戏内 AUC 插件导出的拍卖行价格，
按「最新数据 / 中位数」两种口径，结合 NPC 卖店价，计算各制造专业从当前技能冲到目标技能的
**成本最优路线**，支持逐配方屏蔽 / 确认采用、材料采购清单、路线保存与同服玩家互相分享。

功能参考 [wowplayer.cc](https://wowplayer.cc/)（WLK 版），**配方数据全部以「无限」版本为准**
（来源：[wowforever.wclbox.com 专业库](https://wowforever.wclbox.com/zhuanye)，官方开放 API，客户端版本 1.60.1.70532）。

## 功能一览

| 模块 | 说明 |
| --- | --- |
| 多服务器 | 价格按服务器隔离；同服玩家导入的价格互享，后续计算自动取用 |
| AUC 价格导入 | CSV 上传 / 粘贴；支持 **AUC 拍卖行导出格式**（带物品等级，同名不同物品自动消歧）、文档格式与物品链接格式；每次导入留痕，可手动补价 |
| 模板导出 | 按专业生成 AUC 关注清单（`锻造^铜锭^…`），游戏内导入后按清单导出价格，解决「不知道该导哪些物品」 |
| 价格口径 | 每物品可选「最新数据」（默认）或「中位数」 |
| 路线计算 | 事件驱动贪心：按技能档位（橙/黄/绿/灰）估算涨点概率，最小化「每技能点净成本」 |
| 物品来源 | 材料自动比价：NPC 购买（卖店价，购物清单标注商人出售）vs 拍卖行，取低价 |
| 成品处置 | 卖给拍卖行 / 卖给 NPC / 自用（不计收入），收入自动冲减材料成本 |
| 设计图成本 | AH 可购买的设计图（非拾取绑定）按一次性成本计入冲级总成本；掉落获取的图纸可切换为不计 |
| 配方屏蔽 | 原材料无法获取或成品无法出售时，屏蔽该配方或屏蔽该物品（全链路生效） |
| 确认采用 | 指定必须制作的配方（如想做了卖钱），路线优先排产 |
| 路线分享 | 保存路线生成分享码；他人「采用」后按其服务器当前价格一键重算 |
| 物品图标 | 配方 / 路线 / 材料清单均显示无限版物品图标（官方库 CDN，失败回退原版 wowhead） |
| 数据规模 | 9 个制造专业 · 2150 个配方 · 3979 个物品（2039 个含卖店价、全部带图标） |

## 技术栈

- 后端：Python 3.12 + FastAPI + SQLAlchemy 2.0 + Pydantic v2（SQLite 开发 / PostgreSQL 生产）
- 前端：Vue 3 + TypeScript + Vite + Pinia + Vue Router
- 部署：单容器（后端托管前端构建产物，单端口）或 docker-compose（PostgreSQL）

## 快速开始

### 方式一：Docker Compose（推荐，生产可用）

```bash
docker compose up -d --build
# 首次启动后灌入种子数据（9 专业 / 2150 配方 / 3979 物品）：
docker compose exec app python -m app.seed
# 打开 http://localhost:8000
```

### 方式二：本地开发

```bash
# 1. 后端（Python 3.10+）
cd backend
python -m venv .venv && source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt
python -m app.seed          # 灌库（SQLite，约 5 秒）
uvicorn app.main:app --reload --port 8787

# 2. 前端（另开终端，Node 20+）
cd frontend
npm install
npm run dev                 # http://localhost:5173，/api 自动代理到 8787
```

后端交互文档：http://localhost:8787/docs

### 暴露给朋友访问（cpolar 示例）

```bash
cpolar http 8787            # 本地开发模式
cpolar http 8000            # Docker 模式
```

把生成的公网 URL 发给朋友即可；价格数据存在你自己的机器/数据库里。

## AUC 价格导入格式

游戏内 AUC 插件导出 CSV 后，直接在「价格导入」页上传或粘贴（计算参数行的「价格导入」按钮也可直接导，导完自动重算）。支持三种写法（UTF-8 / GBK 自动识别）：

**1. AUC 拍卖行导出**（推荐，表头 `"价格","名称","物品等级","拥有？","可售数量"`）：

```csv
"价格","名称","物品等级","拥有？","可售数量"
115,"劣质火药",5,"",1169
200,"劣质炸药",20,"",61
90,"劣质炸药",10,"",399
```

- 价格列为铜；「物品等级」用于区分**同名不同物品**（如「劣质炸药」物品等级 10 / 20 是两个不同物品，会分别按各自价格入库）；
- 同名物品若导出未带等级列，则同名物品按同一价格入库，可事后在导入页手动微调。

**2. 文档格式**（表头需包含名称列与价格列，列名兼容 `物品名称/名称/item/name`、`单价/价格/price`）：

```csv
物品名称,单价
铜锭,25
秘银锭,1银20铜
铁锭,1金
```

**3. 物品链接格式**（Auctioneer / TSM 等插件常见，按物品 ID 精确匹配，最可靠）：

```csv
|cff1eff00|Hitem:2840:0:0:0:0:0:0:0|h[铜锭]|h|r,25
|cffffffff|Hitem:3575:0:0:0|h[铁锭]|h|r,80
```

也支持无表头两列（名称,价格）。

价格写法支持：纯数字（铜）、`25银`、`1金23银4铜`、`1g23s4c`、`1.5g`（小数金）。
仓库内置示例：`backend/data/sample_auc_import.csv`。

未匹配到物品库的名称会在导入结果中列出（该物品在无限版不存在或改了名），不影响其他行入库。
单个物品也可以在导入页手动录价。

## 模板导出（AUC 关注清单）

不知道该导哪些物品的价格？在「价格导入」页或「冲级计划」页点**导出模板**：

1. 选专业（可限定技能区间），生成该专业全部配方涉及的物品清单——材料 + 成品 + 设计图，
   输出为 AUC 关注清单文本，第一段是清单名，其余用 `^` 分隔：

   ```text
   锻造^中皮^乌木刀^…^铜锭^…^设计图：铜质链甲外衣^…
   ```

2. 游戏内 AUC 的关注清单导入里粘贴该文本；
3. 在拍卖行按清单浏览，导出价格文本（即上面的 AUC 导出格式），回本工具导入。

API：`GET /api/v1/professions/{key}/watchlist`（可选 `from_skill` / `to_skill` 过滤技能区间）。

## 设计图成本

「无限」版本中大量配方需要先学会设计图（AH 可购买、非拾取绑定）。计算参数行提供：

- **含设计图配方**：是否把设计图配方纳入路线；
- **图纸成本**：`AH 购买计入`（默认）——路线用到该配方时，图纸价格作为**一次性成本**计入总成本
  （学会即消耗，不随制作次数增加；图纸无价格时按 0 计并警告）；`掉落不计`——图纸靠掉落获取，不计价。

被屏蔽的设计图物品同样会让对应配方退出计算。

## 计算规则说明

- **涨点概率**（WoW 经典近似值，`app/config.py` 可调）：橙档 100%、黄档 50%、绿档 25%、灰档 0%。
- **技能档位**直接取自官方数据库：每配方有「学会（橙）/ 变黄 / 变绿 / 变灰」四个阈值。
- **路线算法**：从当前技能出发，在每个事件点（配方档位变化、新配方解锁、到达目标）重新选择
  「每技能点净成本最低」的配方；被「确认采用」的配方优先排产；被屏蔽的配方/物品不参与。
- **净成本** = 材料花费 − 成品收入；材料自动取 NPC 与拍卖行中的低价。
- **设计图成本**：`AH 购买计入` 模式下，路线中每个设计图配方首次使用时将其图纸价作为一次性成本计入
  （材料清单中以「设计图」标出，数量恒为 1）；`掉落不计` 模式不计价。
- 中位数口径下取该物品在本服务器的全部导入记录的中位数（可在配置中加时间窗）。

## API 摘要（/api/v1）

| 方法 | 路径 | 说明 |
| --- | --- | --- |
| GET/POST | `/servers` | 服务器列表 / 新建（同名幂等） |
| GET | `/professions` `/professions/{key}/recipes` | 专业列表 / 配方（可带价格） |
| GET | `/professions/{key}/watchlist` | AUC 关注清单模板导出（可选技能区间） |
| POST | `/prices/import` | AUC CSV 导入（multipart） |
| POST | `/prices/manual` | 单物品手动录价 |
| GET | `/prices` `/prices/item/{id}` `/prices/batches` | 有效价 / 物品价格历史 / 导入批次 |
| POST | `/routes/calc` | 计算路线（屏蔽/确认/图纸成本参数见 `CalcIn`） |
| POST/GET | `/routes` `/routes/{share_code}` `/routes/{share_code}/recalc` | 保存 / 列表 / 详情 / 采用重算 |

## 目录结构

```
WoW-F-BussinessClac/
├── backend/
│   ├── app/
│   │   ├── main.py            # FastAPI 入口（含前端静态托管）
│   │   ├── models.py          # ORM：server/item/profession/recipe/price/saved_route
│   │   ├── schemas.py         # Pydantic 请求响应模型
│   │   ├── config.py          # 环境变量配置（WOWFC_ 前缀）
│   │   ├── seed.py            # JSON 种子灌库
│   │   ├── routers/           # servers / professions / prices / routes / items
│   │   └── services/
│   │       ├── calc.py        # 路线计算引擎（贪心 + 档位概率）
│   │       └── importer.py    # AUC CSV 解析（编码/链接/价格格式）
│   ├── scraper/               # 官方 API 抓取脚本（可重跑更新种子）
│   ├── data/                  # professions.json / items.json / sample_auc_import.csv
│   └── tests/                 # pytest：44 个用例（解析/引擎/API 端到端）
├── frontend/                  # Vue3 + TS 单页应用
│   └── src/components/        # 价格导入 / 模板导出弹窗 / 物品图标
├── Dockerfile                 # 两阶段：构建前端 + Python 后端，单端口
├── docker-compose.yml         # PostgreSQL + app
└── _research/                 # 抓取时的原始页面存档（不随 git 提交）
```

## 更新配方数据（官方数据更新后）

```bash
# 1. 重新下载专业页（需先有更新后的 HTML，或改抓取源）
# 2. 重新抓取（走官方开放 API，限流 5 次/秒，约 10 分钟）
cd backend && python scraper/scrape_professions.py
python scraper/scrape_items.py
python scraper/scrape_icons.py    # 物品图标（详情接口才有，约 13 分钟）
# 3. 重建配方数据（保留服务器/价格/路线）
python -m app.seed --force
```

## 测试

```bash
cd backend && pytest tests/ -q     # 44 passed
```

## 物品图标

物品图标来自无限官方数据库（`/tubiao/<图标名>.jpg`，`inv_ingot_02` / `spell_xxx`
命名与原版同一套体系，无限新增物品原版 wowhead 反而没有），由 `scrape_icons.py`
从官方开放 API 详情接口抓取并随种子入库。前端引用官方 CDN，加载失败自动回退
原版 wowhead 图标 CDN（`wow.zamimg.com`，同一命名）。

## 已知边界 / 后续路线

- 设计图成本为一次性计入，未按「预计制作次数」摊销进单位技能点成本（影响排序权重）；
- 中位数暂为全量记录口径，可加时间窗（`WOWFC_MEDIAN_WINDOW_DAYS`）；
- 暂无账号体系，服务器/路线按昵称署名，分享码即权限；
- 「野营」专业的营地物件配方暂未收录（官方页无配方表）。
