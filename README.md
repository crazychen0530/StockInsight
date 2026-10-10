# StockInsight

StockInsight 是面向个人投资研究的中国 A 股行情与风险分析 Web 平台。当前正在实施 **Milestone 1：基础工程**；后端健康接口可运行，但尚未提供股票行情业务功能。

项目不会连接券商或执行真实交易，不承诺收益，也不会把未经验证的预测作为确定的投资建议。

## 当前状态

- 目标版本：v0.1.0
- 当前阶段：Milestone 0、M1-01、M1-02 已完成；下一任务为 M1-03
- 已建立：项目基线、开发环境、FastAPI 后端、健康接口、SQLAlchemy/Alembic 基础配置及后端测试/检查入口
- 未实现：前端、股票业务 API、数据库业务模型与 migration、行情采集和 Compose 服务

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
├── backend/alembic/              # migration 环境；当前没有 revision
├── backend/app/{api,core,models,schemas,repositories,services,collectors,analysis,jobs}/
├── backend/tests/
├── backend/pyproject.toml
├── frontend/src/{api,components,router,stores,types,views}/
├── frontend/tests/
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

M1-01 曾完整验证 Node.js 22.23.1、Python 3.12 `.venv`、Docker Engine 29.1.3、Docker Compose 2.40.3、Docker daemon 和 PostgreSQL 客户端 16.15。当前 M1-02 会话再次检查时 Docker daemon 不可达或当前进程权限不足；这不影响无数据库依赖的健康接口，但开始 M1-05 前必须重新排查。系统 Node.js 18.19.1 仍保留，不要用全局 Node 升级替代 NVM 项目选择。

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
.venv/bin/python -m pytest backend
.venv/bin/python -c "from app.main import app; print(app.title, app.version)"
.venv/bin/alembic -c backend/alembic.ini heads
```

最后一条命令当前应成功且不输出 revision。Alembic 环境已初始化，但 M1-04 前不得创建股票业务 migration；实际执行 migration 时还需要通过环境变量提供 `DATABASE_URL` 和安装获批的 PostgreSQL 驱动。

## 配置与安全

复制 `.env.example` 形成仅用于本地的 `.env`，但不要提交 `.env`。示例值不能用于生产。生产环境不得公开 PostgreSQL 5432，任何 Token、密码、私钥和证书都不得进入仓库。

## 数据来源与免责声明

首版计划优先通过可替换的 `MarketDataProvider` 接入 AKShare。AKShare 聚合的上游接口、字段和授权条件可能变化；任何公开或商业使用都需要另行核实数据许可。界面和 API 必须展示来源、获取时间和不复权口径。平台数据仅供研究参考，不能替代持牌机构意见。

## GitHub 与部署

项目所有者已提供 GitHub 私有仓库，当前 `main` 跟踪 `origin/main`。后续 push、标签或 Release 仍需明确授权；不会自行创建公开仓库、购买服务器或部署公网。完成 M5 且满足安全、授权、备份恢复和用户公网访问需求后，才评估 M6。
