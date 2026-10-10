# StockInsight

StockInsight 是面向个人投资研究的中国 A 股行情与风险分析 Web 平台。当前仓库只完成 **Milestone 0：项目初始化与长期文档**，尚未提供可运行的行情服务。

项目不会连接券商或执行真实交易，不承诺收益，也不会把未经验证的预测作为确定的投资建议。

## 当前状态

- 目标版本：v0.1.0
- 当前阶段：Milestone 0 已完成，Milestone 1 待开始
- 已建立：项目基线、分层架构、数据口径、数据库/API 草案、任务与安全规则
- 未实现：后端、前端、数据库 migration、实时数据接入和部署

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
├── backend/app/{api,core,models,schemas,repositories,services,collectors,analysis,jobs}/
├── backend/tests/
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

空目录目前使用 `.gitkeep` 保留。这是架构骨架，不代表对应模块已实现。

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

Node.js 22.23.1、Python 3.12 `.venv`、Docker Engine 29.1.3、Docker Compose 2.40.3、Docker daemon 和 PostgreSQL 客户端 16.15 已通过环境检查。系统 Node.js 18.19.1 仍保留，不要用全局 Node 升级替代 NVM 项目选择。

## 开发入口

开始任何任务前请依次阅读：

1. [AGENTS.md](AGENTS.md)：强制开发和会话规则
2. [PROJECT_PLAN.md](PROJECT_PLAN.md)：产品和架构基线
3. [TASKS.md](TASKS.md)：里程碑、状态和验收标准
4. [SESSION_HANDOFF.md](SESSION_HANDOFF.md)：当前可核验状态和下一任务
5. [docs/DECISIONS.md](docs/DECISIONS.md)：长期技术决策及变更流程
6. [docs/architecture.md](docs/architecture.md)：系统边界与数据流
7. [docs/DEPLOYMENT.md](docs/DEPLOYMENT.md)：本地、生产、备份、发布和回滚规划

当前没有依赖安装或启动命令。M1 建立真实工程后再补充可复制的本地启动、migration、测试和停止步骤，避免文档先于实现。

## 配置与安全

复制 `.env.example` 形成仅用于本地的 `.env`，但不要提交 `.env`。示例值不能用于生产。生产环境不得公开 PostgreSQL 5432，任何 Token、密码、私钥和证书都不得进入仓库。

## 数据来源与免责声明

首版计划优先通过可替换的 `MarketDataProvider` 接入 AKShare。AKShare 聚合的上游接口、字段和授权条件可能变化；任何公开或商业使用都需要另行核实数据许可。界面和 API 必须展示来源、获取时间和不复权口径。平台数据仅供研究参考，不能替代持牌机构意见。

## GitHub 与部署

项目所有者已提供 GitHub 私有仓库，当前 `main` 跟踪 `origin/main`。后续 push、标签或 Release 仍需明确授权；不会自行创建公开仓库、购买服务器或部署公网。完成 M5 且满足安全、授权、备份恢复和用户公网访问需求后，才评估 M6。
