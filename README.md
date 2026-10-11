# StockInsight

StockInsight 是面向个人投资研究的中国 A 股行情与风险分析 Web 平台。当前已完成 **Milestone 1：基础工程**；后端健康接口可运行，但尚未提供股票行情业务功能。

项目不会连接券商或执行真实交易，不承诺收益，也不会把未经验证的预测作为确定的投资建议。

## 当前状态

- 目标版本：v0.1.0
- 当前阶段：Milestone 0、M1-01 至 M1-06、M2-01 已完成；下一任务为 M2-02
- 已建立：项目基线、开发环境、FastAPI 健康接口、四张 ORM 模型和初始 migration、Vue/Vite 前端壳及测试入口
- 已新增：本地三服务 Compose、隔离配置、JSON 脱敏日志、统一错误响应和请求关联 ID
- 已新增：[Provider 契约与 AKShare 适配](docs/MARKET_DATA_PROVIDER.md)，包含固定 fixture 离线测试；未验收真实联网采集
- 未实现：股票业务 API、行情采集和行情页面

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

宿主机环境：Node.js 22.23.1、Python 3.12.3 `.venv`、Docker Engine 29.1.3、Compose 2.40.3、PostgreSQL 客户端 16.15。系统 Node.js 18.19.1 仍保留。Codex 沙箱内 Docker socket 访问受限，提升权限后环境检查全部通过。

M1-05 已在官方镜像中验证 Node.js 22.23.3、Python 3.12.15 和 PostgreSQL 16.15。本机 daemon 未配置代理，直接 pull 超时；本次使用从 Ubuntu 官方包提取到 `/tmp` 的 skopeo，经既有 shell 代理下载 Docker Hub 官方镜像并 `docker load` 导入，没有改动系统 daemon 配置或关闭 TLS。前后端构建通过，三服务及容器网络、显式 migration 和 HTTP 链路已验收；后续全新环境验证仍属于 M5。

## 开发入口

开始任何任务前请依次阅读：

1. [AGENTS.md](AGENTS.md)：强制开发和会话规则
2. [PROJECT_PLAN.md](PROJECT_PLAN.md)：产品和架构基线
3. [TASKS.md](TASKS.md)：里程碑、状态和验收标准
4. [SESSION_HANDOFF.md](SESSION_HANDOFF.md)：当前可核验状态和下一任务
5. [docs/DECISIONS.md](docs/DECISIONS.md)：长期技术决策及变更流程
6. [docs/architecture.md](docs/architecture.md)：系统边界与数据流
7. [docs/DEPLOYMENT.md](docs/DEPLOYMENT.md)：本地、生产、备份、发布和回滚规划

## 本地 Docker Compose

从仓库根目录执行。首次下载官方 `postgres:16-bookworm`、`python:3.12-slim-bookworm` 和 `node:22-bookworm-slim` 镜像需要 Docker daemon 能访问 Registry；宿主机 shell 的代理不会自动成为 daemon 的代理配置。镜像获取受阻时先解决网络或导入来源可验证的官方镜像，不能跳过启动验收。

```bash
# 仅首次创建 .env：随机本地密码，权限 0600，不覆盖已有文件
python3 scripts/init_local_env.py
docker compose config --quiet
docker compose up --build --detach --wait --wait-timeout 120

# 显式迁移；API 启动不会创建/修改表
docker compose exec -T api alembic upgrade head
docker compose exec -T api alembic current
docker compose exec -T api alembic check

docker compose ps
curl --noproxy '*' --fail http://127.0.0.1:8000/api/v1/health
curl --noproxy '*' --fail http://127.0.0.1:5173/api/v1/health
curl --noproxy '*' --fail http://127.0.0.1:5173/
```

预期：三个服务均 healthy，migration 为 `0001_initial_schema (head)` 且无模型差异；8000 和经过 Vite 代理的 5173 健康响应均为 `{"status":"ok","version":"0.1.0"}`；首页 HTTP 200。浏览器访问 `http://127.0.0.1:5173/`。API 健康接口仍只表示进程存活，数据库需单独验证。

Compose 使用服务名 `db:5432` 进行容器内部连接；`DATABASE_URL` 不包含密码，通过 `PGUSER`/`PGPASSWORD` 等变量供 psycopg 读取。可在 API 容器验证实际 SQLAlchemy 网络连接：

```bash
docker compose exec -T api python -c 'import os; from sqlalchemy import text; from app.core.database import create_database_engine; engine = create_database_engine(os.environ["DATABASE_URL"]); connection = engine.connect(); print(connection.execute(text("SELECT current_database(), current_user")).one()); connection.close(); engine.dispose()'
```

所有宿主机端口仅绑定 `127.0.0.1`，默认 db/API/web 为 5432/8000/5173；如已被占用，在 `.env` 修改 `POSTGRES_PORT`、`APP_PORT`、`WEB_PORT` 并调整上述 URL。容器内部端口保持 5432/8000/5173。默认项目名为 `stockinsight-local`，数据库卷为 `stockinsight-local_postgres_data`；使用 `docker compose -p <独立项目名>` 时会创建独立网络、容器和卷，相关命令必须保持同一项目名。

后端源码和前端 `src/`、`tests/`、入口及 Vite 配置以只读挂载支持热更新；依赖变更后重新 build。容器采用非 root 应用用户，开发镜像包含测试依赖，不应直接当作生产镜像。Vite 将 `/api` 转发至 `http://api:8000`；宿主机原生 Vite 默认转发至 `http://127.0.0.1:8000`，可用 `API_PROXY_TARGET` 覆盖。页面壳尚不调用 API，代理验证只证明 HTTP 转发链路。

隔离 migration 回归（每次使用新的空库名；不会操作开发库）：

```bash
# 首次可用该名称；重复运行请为数据库名增加唯一前缀，并保持 _migration_test 后缀
docker compose exec -T db sh -c 'createdb -U "$POSTGRES_USER" compose_migration_test'
docker compose exec -T -e TEST_DATABASE_URL=postgresql+psycopg:///compose_migration_test api python -m pytest tests -o cache_dir=/tmp/pytest-cache
docker compose exec -T api ruff check app tests
docker compose exec -T web npm run typecheck
docker compose exec -T web npm test
```

预期后端 38 passed、无 skip，前端 2 个测试通过。migration 测试会删除其专用测试库内的业务表，不能改用开发库名称。

停止和恢复（保留数据库卷）：

```bash
docker compose stop
docker compose up --detach --no-build --wait --wait-timeout 120
# 移除本项目容器与网络时仍保留卷
docker compose down
```

不要执行 `down -v`、`volume prune` 或删除已有数据卷。首次初始化后改变 `.env` 中 PostgreSQL 用户/密码不会修改卷内既有账户；需要按数据库权限流程处理，不能通过删除卷规避。不要将包含凭据的完整 `docker compose config`、容器环境或 `.env` 输出贴入报告。

## 后端安装、运行和验证

以下命令均从仓库根目录执行，只使用现有 `.venv`：

```bash
source .venv/bin/activate
python -m pip install --editable 'backend[dev]'
```

启动开发服务：

```bash
uvicorn app.main:app --app-dir backend --reload --no-access-log --host 127.0.0.1 --port 8000
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

浏览器访问 `http://127.0.0.1:8000/docs` 可使用自动生成的 Swagger UI：查看已实现接口的方法、路径、参数、响应模型，并通过 `Try it out` / `Execute` 发送真实请求。当前只有健康业务接口；文档不是股票业务页面，也不是完整自动化测试。未来带写入/管理能力的接口会真实修改状态，不能把文档按钮当成模拟操作。

运行质量检查和测试：

```bash
.venv/bin/ruff check backend
.venv/bin/python -m pytest backend -m 'not postgres'
.venv/bin/python -c "from app.main import app; print(app.title, app.version)"
.venv/bin/alembic -c backend/alembic.ini heads
```

最后一条命令应输出 `0001_initial_schema (head)`。上述 Pytest 命令运行 37 个非 PostgreSQL 测试；真实 PostgreSQL migration 测试需要按下节单独配置，不能以 metadata 测试代替。

## 数据库迁移与隔离验收

使用 PostgreSQL 16 和已随后端安装的 `psycopg[binary]`；SQLAlchemy URL 的驱动必须为 `postgresql+psycopg`。应用启动不隐式创建表，健康接口也不连接数据库。

以下原生命令假设本机已有 PostgreSQL 16、`stockinsight` 用户及开发库，用户具备目标库 migration 权限（创建验收库还需 CREATEDB 权限）。使用 Compose 的用户优先执行上节容器命令，无需把密码复制到宿主机 shell。原生命令的密码由 libpq 的 `PGPASSWORD` 读取，不写入 URL、命令历史或仓库：

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

预期为 38 passed、无跳过；覆盖配置、日志、错误、关联 ID，以及空库升级、约束、防重、降级/再升级和模型差异。测试拒绝包含既有表的数据库；运行后留下空 `alembic_version` 表，再次验收需要另建一个空的 `*_migration_test` 库。未配置 `TEST_DATABASE_URL` 时 PostgreSQL 用例会明确 skip，不能视为完整验收通过。`downgrade base` 会删除业务表及全部数据，只能用于一次性验收库。

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

优先使用 `scripts/init_local_env.py` 初始化私有 `.env`，不要提交该文件；示例值不能用于生产。Compose 读取 `.env` 并注入容器，Python 配置不自动加载 `.env`，原生运行需显式导出变量。

- `APP_ENV`：`development`（默认）、`test`、`production`；后者只是配置模式，不表示生产安全措施已完成。
- `LOG_LEVEL`：DEBUG/INFO/WARNING/ERROR/CRITICAL；`APP_TIMEZONE` 默认 Asia/Shanghai，JSON 日志时间戳使用 UTC。
- 开发数据库：`DATABASE_URL` 或 `PGHOST`/`PGUSER`/`PGDATABASE`（可选 `PGPORT`/`PGPASSWORD`）；兼容 Compose 无密码 URL 和 libpq 凭据。配置、应用导入及健康接口不隐式连接或迁移数据库。
- 测试数据库：`APP_ENV=test` 下只解析 `TEST_DATABASE_URL`，库名须以 `_test` 结尾，绝不回退开发 URL；破坏性 migration fixture 进一步要求空的 `*_migration_test` 库。共享 fixture 自动切换 test 并移除开发 URL。

所有 API 响应增加服务端生成的 `X-Request-ID`，不回显调用者提交的 ID。错误统一为以下模型；校验错误的可选 `details` 仅包含字段位置和错误类型，不包含输入值和内部异常消息：

```json
{"code":"not_found","message":"Not Found","request_id":"<32 位十六进制 ID>"}
```

应用 JSON 日志包含时间、级别、事件、关联 ID、路由模板、状态和耗时；未知路径仅记 `<unmatched>`，不记录请求体、原始路径、查询串或请求头。内部异常只记录类型和代码位置，绝不记录原始异常消息、源码行或局部变量；凭据和连接串进一步脱敏。禁用 Uvicorn 原始 access log，避免绕过脱敏。日志输出失败时仅向 stderr 输出固定安全提示。后续业务日志必须继续遵守这些限制；第三方库日志需单独审查。

生产环境不得公开 PostgreSQL 5432，任何 Token、密码、私钥和证书都不得进入仓库。访问控制、日志轮转、备份恢复和生产部署仍待后续里程碑。

## 数据来源与免责声明

首版计划优先通过可替换的 `MarketDataProvider` 接入 AKShare。AKShare 聚合的上游接口、字段和授权条件可能变化；任何公开或商业使用都需要另行核实数据许可。界面和 API 必须展示来源、获取时间和不复权口径。平台数据仅供研究参考，不能替代持牌机构意见。

## GitHub 与部署

项目所有者已提供 GitHub 私有仓库，当前 `main` 跟踪 `origin/main`。后续 push、标签或 Release 仍需明确授权；不会自行创建公开仓库、购买服务器或部署公网。完成 M5 且满足安全、授权、备份恢复和用户公网访问需求后，才评估 M6。

### 本地功能分支合并示例

以下命令适用于工作区干净、任务验收通过、功能分支包含目标 main 全部历史且未分叉的情形。M1 已合并并推送 main，三个已合并本地 M1 分支已清理、远程功能分支保留。以下以未来完成的 M2-01 分支为示例，当前还未创建该分支，不能直接执行合并；实际状态见交接文档。

```bash
git status --short --branch
# 有未提交修改时先停下，妥善提交或保存，不要直接覆盖。
git switch main
git merge --ff-only feature/m2-01-market-data-provider
# 按任务范围复核测试及更新 TASKS.md / SESSION_HANDOFF.md，再提交文档。
git log -5 --oneline --decorate
```

`--ff-only` 只允许快进，不产生额外 merge commit，也不会重写原提交；分叉时会拒绝合并，应先检查历史。合并与 push 不同：前者更新本地主分支，后者同步 GitHub。项目所有者自行决定推送时：

```bash
git fetch origin
# 必须成功；失败表示远程 main 不在本地 main 历史中，先检查，不要强推。
git merge-base --is-ancestor origin/main main
git push origin main
git status --short --branch
```

确认 main 已包含完整基础工程后，下一任务从 main 新建 `feature/m2-01-market-data-provider`。本地合并不等于部署，也不会自动执行数据库 migration。
