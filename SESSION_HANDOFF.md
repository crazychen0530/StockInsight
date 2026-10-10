# StockInsight 会话交接

> 更新时间：2026-10-10（Asia/Shanghai）
>
> 本文件记录可核验的当前状态。新会话开始时必须结合 Git、任务清单和实际环境重新确认；不得把规划内容当作已实现功能。

## 1. 当前版本与里程碑

- 目标版本：`v0.1.0`
- 当前完成阶段：Milestone 0；Milestone 1 正在实施
- 当前完成任务：M1-01（环境）、M1-02（后端基础）、M1-03（前端基础）
- 下一任务：M1-04（首版 ORM 模型与初始 Alembic migration）
- 当前交付性质：API 健康接口和前端应用壳可运行；尚无股票查询、行情采集或数据库业务功能

## 2. 当前 Git 状态

- 当前分支：`main`
- 上游分支：`origin/main`
- 本次会话开始时最近提交：`2b31254 feat: initialize backend health API`
- 本次前端基础工程提交：`feat: initialize Vue frontend foundation`
- 远程仓库：`git@github.com:crazychen0530/StockInsight.git`
- GitHub 推送：`origin/main` 当前停留在 `97a83a0`；本次提交后本地预计超前 3 个提交，均未获得本次 push 授权

新会话不得只依赖上述快照，必须执行：

```bash
git status --short --branch
git log -3 --oneline --decorate
git remote -v
```

## 3. 已完成功能

这里的“完成”仅指 M0 项目基础建设：

- 建立 `PROJECT_PLAN.md` 产品、架构、数据和安全基线。
- 建立 `AGENTS.md` 长期开发约束和交付规则。
- 建立 `TASKS.md` 中 M0-M10 里程碑与验收标准。
- 建立 `README.md`、`CHANGELOG.md`、`.gitignore` 和 `.env.example`。
- 建立后端、前端、测试、脚本、文档和基础设施目录骨架。
- 建立系统架构、数据采集、数据库与 API 草案。
- 建立本会话交接、技术决策记录和部署规划。
- 通过现有 NVM 并行安装 Node.js 22.23.1，以 `.nvmrc` 固定 StockInsight 版本；系统 Node.js 18.19.1 保持不变。
- 建立仓库内 Python 3.12.3 `.venv`，并仅在该环境安装 pip 26.2.1。
- 新增 `scripts/check_environment.sh`，统一检测 Node、npm、Python venv、pip、Docker、Compose、daemon 和 PostgreSQL 客户端。
- 安装 Docker Engine 29.1.3、Docker Compose 2.40.3 和 PostgreSQL 客户端 16.15；在 Ubuntu WSL 中启用 systemd，启动 Docker service，并为开发用户启用 docker 组访问。
- 建立 `backend/pyproject.toml`，限定 Python 3.12 并配置 FastAPI、SQLAlchemy 2、Pydantic、Alembic、Uvicorn、Pytest、Ruff 与 `httpx2` 测试客户端。
- 建立 FastAPI 应用工厂、`/api/v1` Router 和 `GET /api/v1/health`；响应只包含 API 状态与应用版本。
- 建立 Pydantic `HealthResponse` 契约和 SQLAlchemy 2 的 Base、延迟 Engine、Session factory 与 session scope。
- 初始化 Alembic 配置、运行环境、revision 模板和空 `versions` 目录，未创建业务 migration。
- 新增 4 个健康接口测试，覆盖 HTTP 200、精确响应结构、状态/版本和敏感配置不泄漏。
- 建立 Vue 3、TypeScript、Vite 与 Vue Router 前端基础工程，并生成锁文件。
- 建立响应式应用壳、明确不展示行情的首页占位和 404 路由。
- 新增 2 个组件/路由测试，覆盖首页壳、免责声明和未知路由。
- 配置类型检查、Vitest、生产构建和 Preview 命令；尚未引入 Pinia、Element Plus、Axios 或 ECharts。

尚未实现股票业务 API、数据库表、Alembic revision、行情采集、指标计算、定时任务或行情业务页面。

## 4. 正在开发的功能

当前没有未提交的在开发功能。M1-03 已通过验收，下一会话从 M1-04 开始。

## 5. 未完成任务

下一阶段优先任务来自 `TASKS.md`：

1. M1-04：确认 `data_sync_jobs` 的范围、计数和断点字段后，创建首个 ORM 模型与 migration。
2. M1-05/M1-06：建立本地 Compose、配置、日志、统一错误和测试 fixture。

不得跳过 M1 直接实现实时行情、AI 预测、自动交易或其他后续范围。

## 6. 最近一次实际测试及结果

本次 M1-02 实际验证结果：

- `./scripts/check_environment.sh`：Node.js、npm、Python `.venv`、pip、Docker CLI、Compose 和 PostgreSQL 客户端通过；Docker daemon 当前不可达或当前进程权限不足，脚本以 1 个失败项退出。
- `.venv/bin/python --version`：Python 3.12.3。
- `.venv/bin/python -m pip install --editable 'backend[dev]'`：安装成功，仅写入仓库 `.venv`。
- `.venv/bin/python -m pip check`：通过，无损坏依赖。
- `.venv/bin/ruff check backend`：通过。
- `.venv/bin/python -m pytest backend`：4 个测试全部通过。
- FastAPI 应用导入：通过，标题 `StockInsight API`、版本 `0.1.0`。
- `httpx2` ASGI 请求：HTTP 200，响应 `{"status":"ok","version":"0.1.0"}`。
- Uvicorn + loopback curl：HTTP 200，响应与契约一致；首次沙箱内请求受网络/代理限制，获批后在非沙箱回环网络复测通过。
- Alembic 配置加载：通过；revision 数 0，SQLAlchemy metadata 表数 0。
- `git diff --check` 与敏感信息扫描：通过。

M1-02 当时未运行前端、数据库连接或 migration 升降级测试；前端基础测试已在下述 M1-03 中补充，数据库 revision 和业务表仍不存在。

本次 M1-03 实际验证结果：

- `./scripts/check_environment.sh`：Node.js 22.23.1、npm 10.9.8、Python、Docker CLI/Compose 和 PostgreSQL 客户端通过；Docker daemon 仍不可达或权限不足。
- `env -u NODE_TLS_REJECT_UNAUTHORIZED npm ci --prefix frontend`：从锁文件全新安装 150 个包成功。
- `npm run typecheck --prefix frontend`：通过。
- `npm test --prefix frontend`：1 个测试文件、2 个测试全部通过。
- `npm run build --prefix frontend`：通过；31 个模块转换，生产产物成功生成。
- Vite Preview + loopback curl：HTTP 200，HTML 标题为 `StockInsight`。
- `npm audit fix` 后复查：0 vulnerabilities，未使用 `--force`。
- `git diff --check`、敏感信息和文档链接检查：通过。

未运行股票业务、数据库连接、migration 升降级或端到端 API 数据测试，因为这些不属于 M1-03。

## 7. 当前已知 Bug

- 当前没有已确认的后端健康接口 Bug。
- Docker daemon 在本次环境中不可达或权限不足；它不影响 M1-02/M1-03，但必须在 M1-05 前重新诊断。
- 外部环境设置了 `NODE_TLS_REJECT_UNAUTHORIZED=0`；该配置会关闭 Node TLS 校验。本次已通过临时取消变量的 Registry ping 和 `npm ci` 验证正常 TLS 可用，后续安装不得依赖该不安全变量。
- 这不代表系统无缺陷；股票 API、数据库、采集和前端业务功能均尚未实现。

## 8. 未解决的技术风险

- Docker daemon 本次复查失败；尚未创建项目 Compose 文件或验证 PostgreSQL 容器及应用服务链路。
- 项目尚未选择和安装 PostgreSQL Python 驱动；应在 M1-04/M1-05 的实际连接设计中明确，不能由健康接口隐式引入。
- AKShare 及其上游接口的稳定性、限流、字段变化和公开/商业使用授权仍需确认。
- 交易日历来源及盘后数据就绪判定尚未选定。
- 股票状态、退市证券和 SH/SZ 代码映射边界尚未形成测试矩阵。
- 不同来源成交量和成交额单位存在映射风险。
- `data_sync_jobs` 的目标范围、成功/失败计数和断点字段尚未定稿。
- 生产负载、数据规模、备份窗口和服务器规格尚无运行数据支持。

## 9. 数据库 Migration 状态

- Alembic 基础环境已初始化，配置可加载。
- 当前 revision 数为 0，`versions/` 只有占位文件；未创建 migration 或数据库表。
- SQLAlchemy `Base.metadata` 当前包含 0 张表；数据库结构仍只是 `PROJECT_PLAN.md` 和 `docs/architecture.md` 中的设计初稿。
- M1-04 必须先确认模型约束和同步任务字段，再创建并测试首个 migration；不得直接修改数据库。

## 10. GitHub 同步状态

- 已配置私有远程仓库 `origin`：`git@github.com:crazychen0530/StockInsight.git`。
- 本地 `main` 已首次推送并设置跟踪 `origin/main`；推送前已确认远程没有既有分支，未覆盖远程历史。
- 本次提交完成后，本地 `main` 预计比 `origin/main` 超前 3 个提交；本次没有 push 授权，因此保持本地未同步。
- 未执行强制推送、版本发布或远程分支删除。
- 后续每个验收通过的功能形成逻辑提交；只有获得当次授权后才执行 push。

## 11. 下一个 Codex 会话的具体任务

可直接复制以下指令：

```text
继续开发 /home/crazychen/myprojects/StockInsight，只执行 Milestone 1 的 M1-04：首版 ORM 模型与初始 Alembic migration。

开始前依次阅读 AGENTS.md、PROJECT_PLAN.md、TASKS.md、SESSION_HANDOFF.md、docs/DECISIONS.md、docs/DEPLOYMENT.md，并检查 git status、最近提交和远程配置。

先运行 ./scripts/check_environment.sh，并检查当前 Git 状态。开始编码前，对照 PROJECT_PLAN.md 第 8 节和 docs/architecture.md 明确 stocks、daily_prices、technical_indicators、data_sync_jobs 的字段、约束、索引和时间/单位语义，尤其先定稿 data_sync_jobs 的目标范围、计数和断点字段。仅实现 SQLAlchemy 2 模型、PostgreSQL 驱动配置、首个 Alembic revision 及 migration 升降级/约束测试；不要实现 Repository、股票 API、采集、前端业务页或 Docker Compose。不得用 SQLite 结果替代 PostgreSQL migration 验收；若 Docker daemon 仍不可用，先报告阻塞和可验证替代方案，不得把未执行的数据库测试写成通过。完成后更新 TASKS.md、SESSION_HANDOFF.md、CHANGELOG.md 和 README.md，形成逻辑完整的本地提交；未经授权不要 push。
```

## 12. 是否达到购买云服务器条件

未达到。M1-M5 尚未完成，没有可运行 MVP、容器部署验证、采集稳定性证据、访问控制、数据授权确认或备份恢复演练。当前继续本地开发，不购买服务器、不部署公网。
