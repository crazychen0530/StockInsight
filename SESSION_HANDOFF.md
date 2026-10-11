# StockInsight 会话交接

> 更新时间：2026-10-11（Asia/Shanghai）
>
> 本文件记录可核验的当前状态。新会话开始时必须结合 Git、任务清单和实际环境重新确认；不得把规划内容当作已实现功能。

## 1. 当前版本与里程碑

- 目标版本：`v0.1.0`
- 当前完成阶段：Milestone 0；Milestone 1 正在实施
- 当前完成任务：M1-01（环境）、M1-02（后端基础）、M1-03（前端基础）、M1-04（ORM 与初始 migration）
- 下一任务：M1-05（本地 Docker Compose 基础工程）
- 当前交付性质：API 健康接口、前端应用壳和初始数据库结构已验收；尚无股票查询或行情采集

## 2. 当前 Git 状态

- 当前分支：`feature/m1-04-initial-schema`（无上游，按 AGENTS.md 使用功能分支）
- 基线：`main` 跟踪 `origin/main`；本次会话开始时 HEAD 为 `3820583 feat: initialize Vue frontend foundation`
- 本次逻辑提交：`feat: add initial PostgreSQL schema`；实际 SHA 以 `git log` 为准，避免在提交自身文档中虚构 SHA
- 远程仓库：`git@github.com:crazychen0530/StockInsight.git`
- GitHub 推送：本地跟踪引用 `origin/main` 停留在 `97a83a0`；`main` 超前 3 个提交，本次功能提交后功能分支比该引用超前 4 个提交。没有 fetch/push，远端实时状态未重新核验

新会话不得只依赖上述快照，必须执行：

```bash
git status --short --branch
git log -3 --oneline --decorate
git remote -v
```

## 3. 已完成功能

完成范围包括 M0 和已验收的 M1-01 至 M1-04：

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
- 初始化 Alembic 配置、运行环境和 revision 模板；M1-04 已新增首个 revision。
- 新增 4 个健康接口测试，覆盖 HTTP 200、精确响应结构、状态/版本和敏感配置不泄漏。
- 建立 Vue 3、TypeScript、Vite 与 Vue Router 前端基础工程，并生成锁文件。
- 建立响应式应用壳、明确不展示行情的首页占位和 404 路由。
- 新增 2 个组件/路由测试，覆盖首页壳、免责声明和未知路由。
- 配置类型检查、Vitest、生产构建和 Preview 命令；尚未引入 Pinia、Element Plus、Axios 或 ECharts。
- 建立 `Stock`、`DailyPrice`、`TechnicalIndicator`、`DataSyncJob` 四张 ORM 模型，首个 revision 为 `0001_initial_schema`。
- 完成 psycopg 3 同步驱动配置、任务范围/计数/恢复游标和同范围活动任务防重索引。
- 在真实 PostgreSQL 16.15 验收升级、主外键/检查约束、防重、降级/再升级和模型无差异检查。

尚未实现股票业务 API、Repository、行情采集、指标计算、定时任务或行情业务页面。

## 4. 正在开发的功能

M1-04 已完成验收；本次收尾形成一个本地功能提交。下一会话先核验 Git 状态，再开始 M1-05。

## 5. 未完成任务

下一阶段优先任务来自 `TASKS.md`：

1. M1-05：解决 Docker 镜像获取问题，建立本地 Compose 并验证 API、前端开发入口和 PostgreSQL 互通。
2. M1-06：统一配置、日志、异常和测试 fixture。

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

M1-02 当时未运行前端、数据库连接或 migration 升降级测试；后续分别在 M1-03 和 M1-04 补充。

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

本次 M1-04 实际验证结果（2026-10-11）：

- `.venv/bin/python --version`：Python 3.12.3；`.venv/bin/python -m pip check`：无损坏依赖。
- 驱动已安装到现有 `.venv`：psycopg/psycopg-binary 3.3.6、SQLAlchemy 2.1.4、Alembic 1.20.0；FastAPI 0.143.0、Pydantic 2.14.0、Pytest 9.1.1、Ruff 0.17.0。
- `./scripts/check_environment.sh`：沙箱中仅 Docker daemon socket 权限项失败；提升权限后重新运行全部通过（daemon 29.1.3 可达）。Docker Hub 拉取 `postgres:16` 因连接被拒绝失败，未建立测试容器。
- 替代验证环境：`apt-get download postgresql-16` 获取 Ubuntu 包，解压至 `/tmp/stockinsight-m1-04-pg.VO77ID`，`initdb` 创建一次性集群，`pg_ctl` 仅监听 127.0.0.1:55432、时区 UTC；`SELECT version()` 确认 PostgreSQL 16.15。未安装系统数据库服务。
- `TEST_DATABASE_URL='postgresql+psycopg://crazychen@127.0.0.1:55432/stockinsight_migration_test' .venv/bin/python -m pytest backend`：9 passed，无跳过。覆盖 migration 升级、约束/主外键、防重、UUID 默认值、定点/时区和空指标、降级/再升级、Alembic `check` 无差异。测试库只存标记为 fixture 的样例数据。
- `.venv/bin/ruff check backend`、格式检查、应用导入、Alembic head 加载、`git diff --check`、文档链接及敏感信息检查通过；未修改前端，本次未重复前端验收。
- 唯一 head：`0001_initial_schema`；测试完成后降级回 base，仅剩空 `alembic_version`。隔离 PostgreSQL 实例在收尾停止，临时下载/集群目录保留用于复核，没有持久开发/生产库。
- 收尾单独运行 Alembic CLI `upgrade head`、`current`、`check`、`downgrade base` 均通过（额外一轮升降级），`current` 返回 `0001_initial_schema (head)`，`check` 返回 `No new upgrade operations detected.`。

## 7. 当前已知 Bug

- 当前没有已确认的后端健康接口 Bug。
- Docker daemon 已启动，提升权限后可达；沙箱 socket 权限受限。Docker Hub 拉取镜像连接失败，M1-05 需解决镜像获取问题。
- 外部环境设置了 `NODE_TLS_REJECT_UNAUTHORIZED=0`；该配置会关闭 Node TLS 校验。本次已通过临时取消变量的 Registry ping 和 `npm ci` 验证正常 TLS 可用，后续安装不得依赖该不安全变量。
- 这不代表系统无缺陷；股票 API、采集和前端业务功能尚未实现。

## 8. 未解决的技术风险

- 尚未创建 Compose 文件或验证 PostgreSQL 容器及应用服务链路，镜像获取受网络限制。
- AKShare 及其上游接口的稳定性、限流、字段变化和公开/商业使用授权仍需确认。
- 交易日历来源及盘后数据就绪判定尚未选定。
- 股票状态、退市证券和 SH/SZ 代码映射边界尚未形成测试矩阵。
- 不同来源成交量和成交额单位存在映射风险。
- 同范围活动任务防重约束已验收；不同范围的重叠任务、过期 running 恢复、断点推进和失败重试仍需 M2/M4 实现。
- 生产负载、数据规模、备份窗口和服务器规格尚无运行数据支持。

## 9. 数据库 Migration 状态

- 唯一 Alembic revision/head 为 `0001_initial_schema`，已在真实 PostgreSQL 16.15 验收。
- SQLAlchemy `Base.metadata` 当前包含 `stocks`、`daily_prices`、`technical_indicators`、`data_sync_jobs` 四张表。
- 已执行两轮升级/降级及无差异检查；临时测试库最终为 base（空版本表），未创建持久开发库。降级会删除四张业务表的数据，只用于一次性库。

## 10. GitHub 同步状态

- 已配置私有远程仓库 `origin`：`git@github.com:crazychen0530/StockInsight.git`。
- 本地 `main` 已首次推送并设置跟踪 `origin/main`；推送前已确认远程没有既有分支，未覆盖远程历史。
- `main` 比本地 `origin/main` 引用超前 3 个提交；本次功能提交在 `feature/m1-04-initial-schema`，完成后比该引用超前 4 个提交，未合并到 main。本次没有 push 授权，因此保持本地未同步。
- 未执行强制推送、版本发布或远程分支删除。
- 后续每个验收通过的功能形成逻辑提交；只有获得当次授权后才执行 push。

## 11. 下一个 Codex 会话的具体任务

可直接复制以下指令：

```text
继续开发 /home/crazychen/myprojects/StockInsight，只执行 Milestone 1 的 M1-05：本地 Docker Compose 基础工程。

开始前依次阅读 AGENTS.md、PROJECT_PLAN.md、TASKS.md、SESSION_HANDOFF.md、docs/DECISIONS.md、docs/DEPLOYMENT.md，并检查 git status、最近提交和远程配置。

先运行 ./scripts/check_environment.sh，确认 M1-04 提交所在 feature/m1-04-initial-schema（尚未合并 main），以包含该提交的功能分支继续。提升权限后 Docker daemon 可达，但 Docker Hub 镜像下载此前失败，先验证并解决镜像获取；不得把无镜像/未启动写成通过。仅实现 API、Vue 开发入口、PostgreSQL 16 的本地 Compose 基础工程和必要 Dockerfile，数据库端口只绑定本机，使用隔离持久卷和环境变量，不提交真实密码。显式执行 Alembic upgrade head，不在应用启动时隐式迁移。实际验证 Compose 配置、启动/健康、容器网络数据库连接、健康接口、前端 HTTP 和 migration 状态；运行涉及的回归测试、Ruff、文档/敏感信息和 Git 检查。不要实现采集、股票 API、Worker/Scheduler 业务或提前执行 M1-06。更新 TASKS.md、SESSION_HANDOFF.md、CHANGELOG.md、README.md 和部署文档；全部通过后形成逻辑本地提交，未经授权不 push、不删除已有数据卷、不部署公网。
```

## 12. 是否达到购买云服务器条件

未达到。M1-M5 尚未完成，没有可运行 MVP、容器部署验证、采集稳定性证据、访问控制、数据授权确认或备份恢复演练。当前继续本地开发，不购买服务器、不部署公网。
