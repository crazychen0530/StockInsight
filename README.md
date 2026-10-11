# StockInsight

StockInsight 是面向个人投资研究的中国 A 股行情与风险分析 Web 平台。当前正在实施 **Milestone 1：基础工程**；后端健康接口可运行，但尚未提供股票行情业务功能。

项目不会连接券商或执行真实交易，不承诺收益，也不会把未经验证的预测作为确定的投资建议。

## 当前状态

- 目标版本：v0.1.0
- 当前阶段：Milestone 0、M1-01 至 M1-04 已完成；下一任务为 M1-05
- 已建立：项目基线、开发环境、FastAPI 健康接口、四张 ORM 模型和初始 migration、Vue/Vite 前端壳及测试入口
- 未实现：股票业务 API、行情采集、行情页面和 Compose 服务

## v0.1.0 计划范围

- A 股基础信息和代码搜索
- 不复权历史日线采集及 PostgreSQL 持久化
- K 线、成交量、MA5、MA20、MA60
- 数据状态、手动补采和盘后增量更新
- 日志、错误处理和自动化测试

AI 涨跌预测、自动交易、券商连接、财报估值、自选股、组合风险和回测均不在首版范围。

## 规划技术栈

- 后端：Python 3.12、FastAPI、SQLAlchemy 2、Alembic、Pydantic、Pandas、NumPy
- 前端：Vue 3、TypeScript、Vite、Element Plus、ECharts、Axios、Pinia
- 数据库：PostgreSQL
- 测试与质量：Pytest、Ruff、TypeScript 类型检查及适当组件测试
- 本地与部署：Docker Compose；未来在用户批准后使用 Nginx/Caddy 和 HTTPS

## 目录

```text
StockInsight/
├── backend/alembic/              # 初始 revision：0001_initial_schema
├── backend/app/{api,core,models,schemas,repositories,services,collectors,analysis,jobs}/
├── backend/tests/
├── backend/pyproject.toml
├── frontend/src/{api,components,router,stores,types,views}/
├── frontend/tests/
├── frontend/package.json
├── frontend/package-lock.json
├── docs/architecture.md
├── docs/DECISIONS.md
├── docs/DEPLOYMENT.md
├── infrastructure/
├── scripts/
├── PROJECT_PLAN.md
├── AGENTS.md
├── SESSION_HANDOFF.md
├── TASKS.md
└── CHANGELOG.md
```

尚未实现的空目录使用 `.gitkeep` 保留。这是架构骨架，不代表对应业务模块已完成。

## 开发前置条件

目标环境为 Ubuntu 24.04、Python 3.12、Node.js 22 LTS、PostgreSQL、Docker Engine 与 Docker Compose。

当前已配置项目隔离环境：

```bash
# 使用 .nvmrc 中已安装的 Node.js 22，不替换系统 Node
export NVM_DIR="$HOME/.nvm"
. "$NVM_DIR/nvm.sh"
nvm use

# 使用仓库内 Python 3.12 虚拟环境
source .venv/bin/activate

# 检查全部前置条件
./scripts/check_environment.sh
```

M1-04 验证环境：Node.js 22.23.1、Python 3.12.3 `.venv`、Docker Engine 29.1.3、Compose 2.40.3、PostgreSQL 16.15。Docker daemon 已由所有者启动，提升权限后可达；当前沙箱内 socket 访问仍受限，Docker Hub 镜像拉取连接失败。migration 使用从 Ubuntu 软件源下载、解压到 `/tmp` 的隔离 PostgreSQL 16.15 实例完成验收。M1-05 仍需验证镜像下载及 Compose 链路。系统 Node.js 18.19.1 仍保留。

## 开发入口

开始任何任务前请依次阅读：

1. [AGENTS.md](AGENTS.md)：强制开发和会话规则
2. [PROJECT_PLAN.md](PROJECT_PLAN.md)：产品和架构基线
3. [TASKS.md](TASKS.md)：里程碑、状态和验收标准
4. [SESSION_HANDOFF.md](SESSION_HANDOFF.md)：当前可核验状态和下一任务
5. [docs/DECISIONS.md](docs/DECISIONS.md)：长期技术决策及变更流程
6. [docs/architecture.md](docs/architecture.md)：系统边界与数据流
7. [docs/DEPLOYMENT.md](docs/DEPLOYMENT.md)：本地、生产、备份、发布和回滚规划

## 后端安装、运行和验证

以下命令均从仓库根目录执行，只使用现有 `.venv`：

```bash
source .venv/bin/activate
python -m pip install --editable 'backend[dev]'
```

启动开发服务：

```bash
uvicorn app.main:app --app-dir backend --reload --host 127.0.0.1 --port 8000
```

在另一个终端请求健康接口：

```bash
curl --noproxy '*' http://127.0.0.1:8000/api/v1/health
```

预期响应：

```json
{"status":"ok","version":"0.1.0"}
```

该响应只证明 API 进程能够处理请求，不声明 PostgreSQL、数据采集器、Docker 或外部数据源健康。

运行质量检查和测试：

```bash
.venv/bin/ruff check backend
.venv/bin/python -m pytest backend -m 'not postgres'
.venv/bin/python -c "from app.main import app; print(app.title, app.version)"
.venv/bin/alembic -c backend/alembic.ini heads
```

最后一条命令应输出 `0001_initial_schema (head)`。上述 Pytest 命令只运行 8 个健康接口和 metadata 测试；真实 PostgreSQL migration 测试需要按下节单独配置，不能以 metadata 测试代替。

## 数据库迁移与隔离验收

使用 PostgreSQL 16 和已随后端安装的 `psycopg[binary]`；SQLAlchemy URL 的驱动必须为 `postgresql+psycopg`。应用启动不隐式创建表，健康接口也不连接数据库。

以下命令假设本机已有 PostgreSQL 16、`stockinsight` 用户及开发库，用户具备目标库 migration 权限（创建验收库还需 CREATEDB 权限）。M1-05 将提供 Compose 启动方式。数据库密码由 libpq 的 `PGPASSWORD` 读取，不写入 URL、命令历史或仓库：

```bash
export PGHOST=127.0.0.1
export PGPORT=5432
export PGUSER=stockinsight
read -r -s -p 'Local PostgreSQL password: ' PGPASSWORD
export PGPASSWORD
export DATABASE_URL='postgresql+psycopg://stockinsight@127.0.0.1:5432/stockinsight'
.venv/bin/alembic -c backend/alembic.ini upgrade head
.venv/bin/alembic -c backend/alembic.ini current
.venv/bin/alembic -c backend/alembic.ini check
```

预期：revision 为 `0001_initial_schema`，`check` 报告无新增升级操作；创建 `stocks`、`daily_prices`、`technical_indicators`、`data_sync_jobs` 四张表。价格/成交额采用定点人民币元，成交量为股，时间戳带时区；字段语义见 [数据字典](PROJECT_PLAN.md#8-数据库设计与数据字典)。活动同步任务索引使用 PostgreSQL 15+ 的 `NULLS NOT DISTINCT`，测试基线为 16。

完整后端验收必须使用独立空库，名称以 `_migration_test` 结尾。以下测试会插入明确标记的 fixture，并执行删除四张表的降级，绝不能指向开发/生产数据：

```bash
createdb stockinsight_migration_test
export TEST_DATABASE_URL='postgresql+psycopg://stockinsight@127.0.0.1:5432/stockinsight_migration_test'
.venv/bin/python -m pytest backend
unset TEST_DATABASE_URL DATABASE_URL PGPASSWORD
```

预期为 9 passed、无跳过；覆盖空库升级、约束、防重、降级/再升级及模型差异。测试拒绝包含既有表的数据库；运行后留下空 `alembic_version` 表，再次验收需要另建一个空的 `*_migration_test` 库。未配置 `TEST_DATABASE_URL` 时 PostgreSQL 用例会明确 skip，不能视为完整验收通过。`downgrade base` 会删除业务表及全部数据，只能用于一次性验收库。

## 前端安装、运行和验证

以下命令从仓库根目录执行，并使用 `.nvmrc` 固定的 Node.js 22：

```bash
export NVM_DIR="$HOME/.nvm"
. "$NVM_DIR/nvm.sh"
nvm use

# 如果外部环境设置了不安全值 0，应在安装依赖前为当前 shell 取消它。
unset NODE_TLS_REJECT_UNAUTHORIZED
npm ci --prefix frontend
```

启动开发服务器：

```bash
npm run dev --prefix frontend -- --host 127.0.0.1
```

运行类型检查、组件测试和生产构建：

```bash
npm run typecheck --prefix frontend
npm test --prefix frontend
npm run build --prefix frontend
```

验证生产构建：

```bash
npm run preview --prefix frontend -- --host 127.0.0.1 --port 4173
curl --noproxy '*' http://127.0.0.1:4173/
```

当前前端只包含应用壳、首页占位和 404 路由，不调用后端、不显示真实或模拟行情。Pinia、Element Plus、Axios 和 ECharts 将在对应功能出现实际需求时再引入。

## 配置与安全

复制 `.env.example` 形成仅用于本地的 `.env`，但不要提交 `.env`。示例值不能用于生产。生产环境不得公开 PostgreSQL 5432，任何 Token、密码、私钥和证书都不得进入仓库。

## 数据来源与免责声明

首版计划优先通过可替换的 `MarketDataProvider` 接入 AKShare。AKShare 聚合的上游接口、字段和授权条件可能变化；任何公开或商业使用都需要另行核实数据许可。界面和 API 必须展示来源、获取时间和不复权口径。平台数据仅供研究参考，不能替代持牌机构意见。

## GitHub 与部署

项目所有者已提供 GitHub 私有仓库，当前 `main` 跟踪 `origin/main`。后续 push、标签或 Release 仍需明确授权；不会自行创建公开仓库、购买服务器或部署公网。完成 M5 且满足安全、授权、备份恢复和用户公网访问需求后，才评估 M6。
