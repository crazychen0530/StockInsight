# StockInsight 会话交接

> 更新时间：2026-10-11（Asia/Shanghai）
>
> 本文件记录可核验的当前状态。新会话开始时必须结合 Git、任务清单和实际环境重新确认；不得把规划内容当作已实现功能。

## 1. 当前版本与里程碑

- 目标版本：`v0.1.0`
- 当前完成阶段：Milestone 0、Milestone 1（六项全部 DONE）与 M2-01/M2-02
- 当前完成任务：M1-01 环境、M1-02 后端、M1-03 前端、M1-04 ORM/migration、M1-05 Compose、M1-06 配置/日志/异常/fixture，以及 M2-01 Provider 契约与 AKShare 适配、M2-02 独立 Validator
- 下一任务：M2-03（股票基础信息同步与搜索持久化）
- 当前交付性质：基础工程已验收，不等于 v0.1.0 MVP 完成；Provider/Validator 已离线验收，尚无股票查询、持久化采集、K 线或均线业务

## 2. 当前 Git 状态

- 当前分支：`feature/m2-02-market-data-validator`，从干净的 M2-01 本地提交 `960a73c` 创建；M2-01 尚未合并 main 或推送。
- 本轮开始执行 `git ls-remote --heads origin main`，确认 GitHub main 与本地 main 基线 `19c6ba41ee7404ec89782c29b2d3aac76ebe2eb6` 一致；远程为 `git@github.com:crazychen0530/StockInsight.git`。
- 本轮代码、测试和文档形成一个本地逻辑提交 `feat: add deterministic market data validation`；准确 SHA 与状态以 `git log -3 --oneline --decorate`、`git status --short --branch` 为准。
- 未 push、未合并 main、未删除分支或卷；M2-01 与 M2-02 两个本地功能提交均待 GitHub 同步，main 仍保留 `19c6ba4`。
- 下一会话须检查 Git 状态、最近提交和远程配置；保留本地功能分支，在获得授权后同步 GitHub。

## 3. 已完成功能

完成范围包括 M0 和已验收的 M1-01 至 M1-06：

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
- 新增 `compose.yaml`，提供 `db`、`api`、`web` 本地服务、项目独立持久卷和本机端口绑定。
- 新增非 root 开发 Dockerfile 与 `.dockerignore`，源码只读挂载支持热更新。
- 新增 `scripts/init_local_env.py`，生成随机本地密码、0600 `.env` 且拒绝覆盖已有文件。
- 新增 Vite `/api` 代理并验证直连、代理和前端 HTTP 链路。
- 本地持久开发库已显式升级至 `0001_initial_schema`，模型无差异；停止/恢复后四张业务表和 revision 保留。
- 统一环境配置与开发/测试库隔离，保留 PG* 和无密码 URL；配置加载/健康检查不连接或迁移数据库。
- 建立 `ErrorResponse`、公开应用错误、HTTP/校验/未知异常处理，以及服务端生成的 `X-Request-ID`。
- 建立应用 JSON 日志与脱敏；只记录路由模板和安全上下文，不输出原始请求、异常消息或内部堆栈；未知异常仅记录类型和单一源位置。
- 建立共享应用/客户端/独立数据库 fixture，增加配置、错误、脱敏、并发和日志输出失败测试；完整后端测试 38 项。

M2-01 新增：

- `MarketDataProvider` Protocol、不可变 StockInfo/DailyBar/MarketDataBatch，批次保留来源、接口、UTC 获取时间、不复权和 CNY/股单位。
- AkShareProvider 基础信息与日线映射；基础列表显式排除北京市场，未知上市日期/状态保留 None/unknown；日线手转股、Decimal 和请求闭区间相关性检查。
- `market-data` 可选 extra 固定 AKShare 1.19.1；Settings 支持 MARKET_DATA_TIMEOUT_SECONDS（默认 30 秒）。私有 SDK 子进程限制整次调用并在超时后终止回收，复用公开错误与安全日志。
- 明确标记的模拟 fixture、可替换 mock Provider 与真实子进程离线测试；详见 [Provider 专题](docs/MARKET_DATA_PROVIDER.md)、ADR-012。

M2-02 新增：

- `collectors/validator.py` 提供 normalize_symbol、validate_date_range、validate_stocks、validate_daily_prices 与安全 MarketDataValidationError；无网络、Web、ORM、SDK、Pandas 或配置/日志依赖。
- 复用 Provider DTO；校验支持代码段、日期区间/重复、OHLCV、元数据、单位、不复权与精确存储范围，返回排序的新批次，UTC 转换保留时刻，unknown 不猜测；成交量不重复换算。
- Decimal digits/exponent 检查独立于调用者 context，不舍入，移除数值不变的冗余尾零/零 exponent；显式 date set 日历接口，未提供时仅做周末/范围等日期检查。
- 新增 143 项固定模拟测试及 Provider fixture 组合验证；专题见 [Validator 文档](docs/MARKET_DATA_VALIDATOR.md)、ADR-013。

尚未实现股票业务 API、Repository、持久化采集、指标计算、定时任务或行情业务页面。Provider 成功不表示校验或存储成功；Validator 通过不证明真实证券存在、完整日历/缺日验收或市场报价真实性。

## 4. 正在开发的功能

M2-01/M2-02 已完成并本地提交；本次结束保持原有三服务运行。M2-03 待下一任务启动。

## 5. 未完成任务

下一阶段优先任务来自 `TASKS.md`：

1. M2-03：基础信息同步/持久化及搜索；复用 Provider 与 Validator，保留已确认上市信息，不根据快照缺席推断退市。
2. M2-04 至 M2-05：日线幂等采集、本地 CLI 和任务记录。
3. M3：股票查询 API、搜索/详情页、K 线与成交量；M4：均线和自动更新；M5：完整 MVP 验收。

按里程碑推进，不提前实现实时行情、AI 预测、自动交易或其他未批准范围。

## 6. 最近一次实际测试及结果

最新：M2-02 Validator 离线验收（2026-10-11）：

- `./scripts/check_environment.sh`（提升权限）：全部通过；开始检查三服务均 healthy，远程 main 与本地 main `19c6ba4` 一致。以本地 `960a73c` 创建 M2-02 分支。
- 开始时 M2-01 回归：90 passed、1 deselected，`pip check` 无损坏依赖。本轮不安装或新增任何依赖。
- `.venv/bin/ruff check backend`、`.venv/bin/ruff format --check backend`：通过（37 files formatted）；`.venv/bin/python -m pytest backend -m 'not postgres' -q`：**233 passed、1 deselected**（排除 PostgreSQL），包含新增 143 项模拟值/fixture 测试。
- 独立 Python 进程导入 Validator 后检查 sys.modules：没有 fastapi/sqlalchemy/pandas/akshare，纯逻辑分层通过；默认测试不访问实时行情。
- 首轮有两个负例因辅助函数把 list 转成合法 tuple 而失败；修正负例构造后全量通过。额外验证了极大 exponent 的零和冗余尾零精确规范化，不舍入且原始 DTO 保留。
- 无模型、migration、前端、Compose 或 Provider 实现变更；未运行本轮数据库升降级/前端测试，未连接或修改开发库，原卷保留。
- 收尾 `docker compose ps`：三服务均 healthy；8000 直连与 5173 代理健康契约和 32 位请求 ID 通过，OpenAPI 仍只含健康业务接口。
- 最终文档相对链接/围栏、敏感信息/生成物排除、`git diff --check` 和 Git 状态检查通过；代码/测试/文档形成本地逻辑提交，未 push 或合并 main。


最新：M2-01 Provider 离线验收（2026-10-11）：

- `./scripts/check_environment.sh`：沙箱内 Docker socket 项受限；提升权限后全部通过。`git ls-remote --heads origin main` 与本地基线 `19c6ba4` 一致；`docker compose ps` 开始与结束均为三服务 healthy。
- `.venv/bin/python -m pip install --editable 'backend[dev,market-data]'`：成功，安装 AKShare 1.19.1、Pandas 3.0.6、NumPy 2.5.4 等到项目 venv；未变更系统 Python 或 API 镜像。`pip check`：No broken requirements found。
- 本地只导入 AKShare 并使用 inspect.signature 核验基础信息与日线签名，符合官方文档；未调用真实行情接口。
- `.venv/bin/ruff check backend`：通过；`.venv/bin/ruff format --check backend`：35 files already formatted。
- `.venv/bin/python -m pytest backend -m 'not postgres' -q`：**90 passed、1 deselected**，包含新增 53 项离线测试及已有 37 项回归；不依赖实时网络。DataFrame 日期序列化与 fake SDK 真子进程调用、超时实际终止/回收、输出与异常脱敏均通过。
- 测试过程：新增 HTTP 错误 fixture 最初使用同步路由，在沙箱线程执行处停滞；改成异步 fixture 后完整回归通过。两个旧测试进程经精确 PID 确认后已终止，未操作 Compose 服务。
- 真实 HTTP 8000 直连与 5173 代理健康接口均为 200，成功契约保持 status/version，X-Request-ID 为 32 位；OpenAPI 仅 `/api/v1/health`。
- 无数据库模型、migration、前端或 Compose 实现变化；未运行本轮 PostgreSQL 升降级/前端测试，原开发库与卷保留。现有 API 镜像未装可选 SDK；未来 Worker 镜像需显式安装 extra。
- 文档链接/代码围栏、敏感信息与生成物排除、`git diff --check`、最终 Git 状态检查通过，代码/测试/文档形成本地逻辑提交；未 push。


最新：main 同步与本地分支清理复核（2026-10-11）：

- `.venv/bin/ruff check backend`：通过；`.venv/bin/python -m pytest backend -m 'not postgres' -q`：37 passed、1 deselected。本轮仅 Git 管理及文档，不重复前端/数据库测试，没有修改代码、依赖、数据库或容器。
- `git fetch origin` 与 `git merge-base --is-ancestor origin/main main`：通过；对三个指定本地分支分别执行祖先检查：均已合并 main，无其他 worktree 占用。
- 推送前检查 8 个待推送提交、118 个唯一 blob：未发现本地真实数据库密码、私钥或 Token 模式，未跟踪真实 `.env`。
- `git push origin main`：成功；`git ls-remote --heads origin main feature/m1-06-runtime-foundation`：main 为 `733e63d92745e22d699b97a03604292518e585b2`，与本地相同；远程功能分支仍为 `b0c4fe641513aa4c663e4c0b7749bf1b414b7836`。
- 确认成功后执行 `git branch -d feature/m1-04-initial-schema feature/m1-05-local-compose feature/m1-06-runtime-foundation`：三个本地分支删除成功，`git branch -a` 仅显示本地 main 和原有两个远程跟踪分支。
- 更新本轮文档记录后再次检查 Markdown 链接/围栏、敏感信息与 `git diff --check`，提交并同步 main；实际最新 SHA 和工作区状态以最终 Git 检查为准。

此前 M1 合并后复核（2026-10-11）：

- `git merge --ff-only feature/m1-06-runtime-foundation`：成功，无冲突；`git diff --exit-code feature/m1-06-runtime-foundation HEAD`：通过（更新本轮文档前，合并后的代码树完全相同）。没有改业务代码、依赖、数据库或运行容器。
- `.venv/bin/ruff check backend`、`.venv/bin/ruff format --check backend`：通过；`.venv/bin/python -m pytest backend -m 'not postgres' -q`：37 passed、1 deselected。
- `docker compose exec -T web sh -c 'npm run typecheck && npm test'`：类型检查通过、2 tests passed；`docker compose ps`：三服务 healthy。
- 真实 HTTP `/docs`：200，确认为 Swagger UI；`/openapi.json` 仅列出 `/api/v1/health`；健康接口 200，精确返回现有状态/版本契约。
- `git ls-remote --heads origin main feature/m1-06-runtime-foundation`：远程 main 为 `97a83a0`、功能分支为 `b0c4fe6`。本轮未执行 push。
- 本轮没有重复数据库升降级和前端构建：无代码树变化，保留前一次完整验收结果，不能将其描述为本轮重新执行。

此前 M1-06 实际验证结果（2026-10-11）：

- `.venv/bin/ruff check backend`、`.venv/bin/ruff format --check backend`：通过；`.venv/bin/python -m pytest backend -m 'not postgres' -q`：37 passed、1 deselected（明确排除 PostgreSQL 用例）。
- `docker compose build api`：成功，沿用官方镜像和已有依赖，无新增包；`docker compose up --detach --no-build --wait --wait-timeout 120`：三服务 healthy，开发库和原数据卷保留。
- 新建独立空库 `m1_06_20261011_1527_migration_test`；`docker compose exec -T -e TEST_DATABASE_URL=postgresql+psycopg:///m1_06_20261011_1527_migration_test api python -m pytest tests -o cache_dir=/tmp/pytest-cache -q`：38 passed，无 skip，包含空库升降级和日志集成。
- API 容器 `python -m pip check`、`ruff check app tests`、`ruff format --check app tests`：通过；`alembic current` 为 `0001_initial_schema (head)`，`alembic check` 无差异。
- `docker compose exec -T web sh -c 'npm run typecheck && npm test && npm run build'`：类型通过、2 tests passed、31 modules 构建通过。
- 真实 HTTP：5173 首页与 8000 `/docs` 均 HTTP 200；8000 直连和 5173 代理健康响应精确不变，带 32 位服务端 ID；404 的错误体与响应头关联 ID 一致，OpenAPI 只有健康业务路由。
- 容器日志读取并解析为 JSON：原始路径/查询中的 fixture 敏感标记未出现。内部异常脱敏由专用 ASGI 测试覆盖，不增加生产测试路由。
- 本轮修复的测试发现：非法 URL 异常类型遗漏；stdout 切换使日志输出到已关闭流；完整 migration 回归暴露 Alembic 默认禁用已有日志。已分别统一安全异常、动态安全 stdout handler、`disable_existing_loggers=False`，最终完整回归通过。第一次完整库 `m1_06_20261011_1525_migration_test` 不重置，第二次使用另一个新空库。
- 最终镜像无源码挂载、无网络独立执行 `docker run --rm --network none stockinsight-local-api:latest python -m pytest tests -m 'not postgres' -o cache_dir=/tmp/pytest-cache -q`：37 passed、1 deselected；再次启动 Compose 全部 healthy，配置化 Engine 实际连接开发库，head 和四张空业务表保留。
- Markdown 相对链接（12 项）/围栏、76 个源码/文档文件敏感信息及生成物排除、待推送历史 5 个既有提交的 89 个唯一 blob、`git diff --check`：通过。本地真实数据库密码未出现在扫描文件或历史中；`.env`、venv、node_modules、dist 保持忽略。GitHub 实际同步见第 10 节。

本轮没有新增 migration，也没有采集真实股票数据。容器/HTTP 冒烟不等于完整浏览器端到端业务验收。

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

本次 M1-05 实际验证结果（2026-10-11）：

- `./scripts/check_environment.sh`：沙箱内 Docker socket 权限项失败；提升权限后全部通过，daemon 可达。
- daemon 直接 `docker pull postgres:16-bookworm` 超时；从 Ubuntu 官方包仅提取 skopeo 和依赖到 `/tmp/stockinsight-m1-05-tools.9yTIBO`，经已有 shell 代理下载 Docker Hub 官方 postgres/Python/Node 镜像后 `docker load` 成功。下载中曾出现 EOF，工具续传后成功；未修改系统 Docker 配置、未关闭 TLS。
- `docker compose config --quiet` 通过；缺少密码时拒绝配置解析。JSON 检查确认三个服务、服务名 DNS、健康依赖、本机端口与项目隔离卷。
- `python3 scripts/init_local_env.py` 创建被 Git 忽略的 0600 `.env`；再次执行拒绝覆盖，校验和保持不变。密码不输出、不进入提交。
- `docker compose build web` 和 `docker compose build api` 成功；Compose 提示 buildx 未安装，内置 builder 仍完成构建。镜像版本为 Node.js 22.23.3、Python 3.12.15、PostgreSQL 16.15。
- 宿主机 Ruff 与 8 个非 PostgreSQL 后端测试通过；前端类型检查、2 个测试和构建通过。
- `docker compose run --rm --no-deps web sh -c 'node --version && npm run typecheck && npm test && npm run build'` 全部通过（2 tests，31 modules）。容器 `npm ci` 报告 0 vulnerabilities。
- 后端容器的 `pip check`、Ruff、格式检查、8 个非数据库测试通过；非 root 用户与只读挂载可用。
- `docker compose up --detach --no-build --wait --wait-timeout 120`：db/API/web 均 healthy；实际端口分别为 `127.0.0.1:5432`、`:8000`、`:5173`。
- `docker compose exec -T api alembic upgrade head/current/check`：达到 `0001_initial_schema (head)`，`No new upgrade operations detected.`。
- API 容器通过 SQLAlchemy/libpq 实际连接 `db:5432` 的 `stockinsight` 库；确认 PostgreSQL 16.15 和四张业务表。
- loopback HTTP：8000 直连与 5173 `/api/v1/health` 代理均 HTTP 200 且精确返回健康契约；5173 首页、入口模块和 Vue 源模块均 HTTP 200。
- 新建独立 `m1_05_20261011_migration_test` 库，`docker compose exec -T -e TEST_DATABASE_URL=postgresql+psycopg:///m1_05_20261011_migration_test api python -m pytest tests -o cache_dir=/tmp/pytest-cache`：9 passed，无 skip；仅该测试库执行破坏性升降级，开发库不受影响。
- `docker compose stop` 后，首次 `start --wait` 因当前版本不支持该参数失败；已修正文档并以 `up --detach --no-build --wait --wait-timeout 120` 恢复。恢复后 revision 和四张业务表仍在，`daily_prices` 行数为 0。
- 文档链接/围栏、`git diff --check`、敏感信息与构建上下文检查通过；本轮不增加业务表或新的 migration。

本次验收是基础设施与已有功能回归，不等于股票数据端到端业务验收或全新 Linux 环境部署验收。

## 7. 当前已知 Bug

- 当前没有已确认的后端健康接口或 Provider/Validator 离线契约 Bug；真实上游尚未验收。
- Docker daemon 已启动，提升权限后可达；沙箱 socket 权限受限。daemon 直接拉取 Docker Hub 仍超时；本次通过用户态代理下载并导入官方镜像完成验收，系统 daemon 代理问题未作全局修改。
- 外部环境设置了 `NODE_TLS_REJECT_UNAUTHORIZED=0`；该配置会关闭 Node TLS 校验。本次已通过临时取消变量的 Registry ping 和 `npm ci` 验证正常 TLS 可用，后续安装不得依赖该不安全变量。
- 这不代表系统无缺陷；完整日历、股票 API、持久化采集和前端业务功能尚未实现。

## 8. 未解决的技术风险

- 本地 Compose 已验收；全新环境复现、生产部署、备份恢复和依赖/镜像完全锁定仍待 M5/M6。新镜像获取可能需要代理或官方镜像导入。
- AKShare 及其上游接口的稳定性、限流、字段变化和公开/商业使用授权仍需确认。
- 交易日历来源及盘后数据就绪判定尚未选定。
- M2-02 已形成支持代码段/市场/未知状态测试矩阵；完整证券存在性、退市状态生命周期与新代码段扩展仍需后续确认。
- 不同来源成交量和成交额单位存在映射风险。
- 同范围活动任务防重约束已验收；不同范围的重叠任务、过期 running 恢复、断点推进和失败重试仍需 M2/M4 实现。
- 生产负载、数据规模、备份窗口和服务器规格尚无运行数据支持。

## 9. 数据库 Migration 状态

- 唯一 Alembic revision/head 为 `0001_initial_schema`，已在真实 PostgreSQL 16.15 验收。
- SQLAlchemy `Base.metadata` 当前包含 `stocks`、`daily_prices`、`technical_indicators`、`data_sync_jobs` 四张表。
- 已执行两轮升级/降级及无差异检查；临时测试库最终为 base（空版本表），未创建持久开发库。降级会删除四张业务表的数据，只用于一次性库。
- 上一条为 M1-04 历史状态。M1-05 当前持久开发库 `stockinsight` 已达到 head，四张业务表为空；卷为 `stockinsight-local_postgres_data`，本次没有删除数据卷。
- M1-05 独立测试库 `m1_05_20261011_migration_test` 完整验收后为 base（仅空版本表）；重复测试须创建新的空 `*_migration_test` 库，不能指向开发库或删卷重置。
- M1-06 未新增 revision；新建的两个独立测试库均完成 migration 测试并回到 base，仅空版本表；开发库仍为 head，四张业务表为空。

## 10. GitHub 同步状态

- 已配置私有远程仓库 `origin`：`git@github.com:crazychen0530/StockInsight.git`。
- 本地 `main` 已首次推送并设置跟踪 `origin/main`；推送前已确认远程没有既有分支，未覆盖远程历史。
- 当前 main 已完成完整 M1 同步，最终基线 `19c6ba4` 已在本轮开始重新核验；此前同步/清理已结束。本轮 M2-02 从 M2-01 本地提交继续；两个功能提交均尚未同步 GitHub。
- 远程 `feature/m1-06-runtime-foundation` 保持 `b0c4fe641513aa4c663e4c0b7749bf1b414b7836`，未删除或改写；m1-04/m1-05 未单独建立远程分支，其提交已随完整 M1 进入远程 main。
- 三个本地 M1 功能分支已在确认同步成功且全部合并后，以 `git branch -d` 安全删除；没有强制删除、删除代码、重写历史、创建 PR/Release 或发布公网。
- 未执行强制推送、版本发布或远程分支删除。
- 后续每个验收通过的功能形成逻辑提交；只有获得当次授权后才执行 push。

## 11. 下一个 Codex 会话的具体任务

可直接复制以下指令：

```text
继续开发 /home/crazychen/myprojects/StockInsight，只执行 M2-03：实现股票基础信息同步与搜索持久化。

依次阅读 AGENTS.md、PROJECT_PLAN.md、TASKS.md、SESSION_HANDOFF.md、docs/DECISIONS.md、docs/DEPLOYMENT.md、docs/MARKET_DATA_PROVIDER.md 和 docs/MARKET_DATA_VALIDATOR.md；检查 Git 状态、最近提交和远程配置。

核验本地 feature/m2-02-market-data-validator 已验收提交，若尚未合并 main，以该提交创建 feature/m2-03-stock-persistence，保留 main，不擅自合并或 push。复用 MarketDataProvider 与纯函数 Validator，实现 Application Service -> Repository -> Database 的基础信息同步与代码/名称搜索持久化，不新增业务 HTTP API（留 M3）、日线采集（M2-04）、CLI/任务状态/重试（M2-05）或前端。重复同步幂等；明确新记录与更新的处理，不以 unknown/None 覆盖已有已确认状态/上市日期，不根据本次缺席猜测退市。测试默认使用固定 fixture/mock Provider；数据库集成仅用新建独立测试库，完整 migration 回归仅用新空 *_migration_test 库；保留开发库 stockinsight 与原卷，不擅自改 Schema。若需架构/数据口径变更，先记录 Proposed 决策等待确认。完成适当单元/真实数据库集成测试、任务/交接/变更文档与逻辑提交；未经授权不 push、不合并 main、不删卷、不部署公网。报告下一任务与服务器需求。
```

## 12. 是否达到购买云服务器条件

未达到。M1 本地基础工程和容器验证、M2-01/M2-02 离线契约已完成，但 M2 其余任务及 M3-M5 尚未完成；没有可验收的完整 MVP、采集稳定性证据、访问控制、数据授权确认或备份恢复演练，也未决定需要公网访问。当前继续本地开发，不购买服务器、不部署公网。

## 13. 当前可见的本地页面

- 首页：`http://127.0.0.1:5173/`，基础应用壳与免责声明，无搜索/行情/K 线。
- API 文档：`http://127.0.0.1:8000/docs`，当前只有健康业务接口。
- 健康：`http://127.0.0.1:8000/api/v1/health`，也可通过 5173 同路径代理。
- 三服务保持运行，仅本机可访问；在开发电脑浏览器打开。若会话后重启电脑，先执行 `docker compose up --detach --no-build --wait --wait-timeout 120`。实际浏览器交互/Windows 网络透传未单独验收。
