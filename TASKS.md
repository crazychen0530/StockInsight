# StockInsight 开发任务

状态枚举：`TODO`、`IN PROGRESS`、`DONE`、`BLOCKED`。只有实现完成、验收命令通过且文档同步后才能标记 `DONE`。

## 首版后：股票入门教育（2026-10-13 用户授权）

- DONE OPS-PUBLIC-01 修复public在临时域名解析失败时过早退出并缺少诊断信息（2026-10-14）。
  - Git交付：336028f已独立快进合并main并正常推送origin/main；隔离main运维35项通过，上一轮scheduler与Windows CA未提交改动保留于原工作区。
  - 实际失败为registered后curl6，后续域名可解析；新增约120秒限时DNS/HTTPS启动等待、脱敏错误类别与证据路径，保持TLS与全部只读门禁。36项运维测试、Ruff、bash语法及diff检查通过；60秒公网演练通过11项本地和19项公网门禁并清理。不改Schema/依赖/既有部署，不将短时验证当作8小时稳定性验收。

- DONE EDU-01 主页增加零基础学习入口与股票学习中心。
  - 验收：六课覆盖股票/行情/K线/成交量与MA/基本面概念/交易流程与风险；教学图示明确非真实行情；词典支持搜索；测验有解释、纠错与重置；前端类型、组件、构建及桌面/手机浏览器验证通过；不新增依赖、API、Schema或交易功能。
  - 验收结果：Node22类型检查、44项前端测试、构建通过；隔离Chromium实测首页行情离线入口、课程锚点、K线切换、测验纠错、术语搜索、直接刷新、390px无横向溢出与键盘操作通过，无页面脚本错误。官方浏览器断续下载后经完整大小/ZIP CRC校验，缺失运行库仅解压于/tmp，未修改系统安装。详见docs/STOCK_LEARNING.md。
  - 已于后续 EDU-02 发布到现有本地生产代理，未自动开启公网窗口。
- DONE EDU-02 学习页体验优化与现有前端发布（2026-10-13 用户明确授权更新、验证、合并推送）。
  - 增加返回目录、清空搜索、测验完成提示；44项组件测试、类型检查及只读生产构建通过。
  - 仅更新 proxy，部署后 HTTPS/认证/重定向/只读11项通过，生产浏览器学习流程、390px、键盘、真实图表通过；API/DB/scheduler/monitor/backup未重启。首次启动即刻探测连接重置，后续验证通过，不宣称零中断。
  - 原镜像保留可回滚，无依赖、API、Schema/migration变化。Git合并/推送结果见 SESSION_HANDOFF.md 最新记录。

## Milestone 0：项目初始化与长期文档

- DONE M0-01 检查工作空间、工具版本和现有文件。
  - 验收：记录 Python、Node、Docker/Compose 可用性；确认未覆盖已有项目。
- DONE M0-02 创建并初始化独立 `StockInsight` Git 仓库。
  - 验收：仓库位于 `StockInsight/`，默认分支为 `main`；未猜测远程地址，后续仅使用项目所有者提供的私有仓库。
- DONE M0-03 建立长期项目文档。
  - 验收：`PROJECT_PLAN.md` 覆盖产品、技术、数据、安全、里程碑、同步和部署基线；`AGENTS.md` 可指导后续开发。
- DONE M0-04 建立任务、变更记录和项目入口文档。
  - 验收：`TASKS.md` 含全部里程碑和可验证标准；`CHANGELOG.md`、`README.md` 内容一致。
- DONE M0-05 建立安全的仓库基础文件与目录骨架。
  - 验收：`.gitignore`、`.env.example` 和所需目录存在；无业务实现和真实密钥。
- DONE M0-06 建立架构、采集、数据库和 API 草案。
  - 验收：`docs/architecture.md` 含可解析 Mermaid 图和关键调用边界；与 `PROJECT_PLAN.md` 无已知冲突。
- DONE M0-07 完成文档与 Git 安全校验。
  - 验收：内部 Markdown 链接、敏感信息模式、空目录占位和 Git 状态检查通过；如实记录环境缺口。
- DONE M0-08 建立长期会话交接、技术决策和部署管理规范。
  - 验收：`SESSION_HANDOFF.md` 反映真实项目状态；`docs/DECISIONS.md` 记录八项初始决策；`docs/DEPLOYMENT.md` 明确本地、生产、备份、发布和回滚边界；`AGENTS.md` 包含会话首尾与架构一致性检查规则；文档校验通过。
- DONE M0-09 配置项目所有者提供的 GitHub 私有远程并完成首次同步。
  - 验收：推送前确认远程为空；`main` 成功推送并跟踪 `origin/main`；未强制推送、未覆盖远程历史、未发布版本。

## Milestone 1：前端、后端、数据库基础工程

- DONE M1-01 将本地 Node 升级至兼容的 22 LTS，并安装/验证 Docker Engine 与 Compose。
  - 验收：版本命令通过，记录安装方式，不提交本机专用配置。
  - 验收结果：Node.js 22.23.1 通过 NVM 与 `.nvmrc` 隔离；Python 3.12.3 `.venv`、Docker 29.1.3、Compose 2.40.3、可达的 Docker daemon 和 PostgreSQL 客户端 16.15 均通过 `scripts/check_environment.sh` 验证。
- DONE M1-02 初始化 FastAPI、SQLAlchemy 2、Pydantic、Alembic、Pytest 与 Ruff 工程。
  - 验收：应用可启动，`GET /api/v1/health` 返回契约响应，lint 和测试通过。
  - 验收结果：Python 3.12 后端以 `pyproject.toml` 管理；健康接口仅返回 API 进程状态与版本；SQLAlchemy Base/Engine/Session 基础配置和无 revision 的 Alembic 环境已建立；Ruff、4 个 Pytest 用例、应用导入、ASGI 请求及真实 Uvicorn HTTP 请求均通过。
- DONE M1-03 初始化 Vue 3 + TypeScript + Vite 前端。
  - 验收：开发构建可启动，类型检查和基础组件测试通过。
  - 验收结果：Node.js 22 下建立 Vue 3、TypeScript、Vite 与 Vue Router 基础工程；首页壳和 404 路由不展示行情；锁文件全新安装、类型检查、2 个组件/路由测试、生产构建、Preview HTTP 冒烟和 npm 0 漏洞审计通过。
- DONE M1-04 定义首版 ORM 模型并创建初始 Alembic migration。
  - 验收：四张核心表的主外键、约束、索引和单位语义与规划一致；空库升级测试通过。
  - 验收结果（2026-10-11）：四张 ORM 模型、psycopg 3 驱动和 `0001_initial_schema` 已实现；真实隔离 PostgreSQL 16.15 上空库升级、主外键/检查约束、活动任务防重、降级/再升级和 Alembic 无差异检查通过；后端 9 个测试全通过，Ruff 通过。
- DONE M1-05 创建本地 Docker Compose 基础工程。
  - 验收：API、前端开发入口和 PostgreSQL 可在本地互通；数据库不对非本机公开。
  - 验收结果（2026-10-11）：三服务构建和 healthy 检查通过；实际端口仅绑定 127.0.0.1；API 容器 SQLAlchemy 连接 PostgreSQL 16.15、显式 Alembic upgrade/current/check、API 直连/Vite 代理/前端 HTTP 均通过；独立空库后端 9 passed 无跳过，容器前端类型检查/2 个测试/构建通过；停止后恢复验证 revision 和表保留，未删除数据卷。本机 daemon 直连 Registry 超时，经用户态代理下载官方镜像并导入完成验收。
- DONE M1-06 建立统一配置、日志、异常和测试 fixture。
  - 验收：开发/测试配置隔离，日志脱敏，错误模型有测试。
  - 验收结果（2026-10-11）：环境白名单与独立测试 URL、JSON 脱敏日志、统一错误模型、服务端请求 ID 和共享 fixture 已实现，无新增依赖/数据库结构。宿主机 37 个非 PostgreSQL 测试通过；Compose 独立新空库完整后端 38 passed 无跳过，包含 Alembic 升降级后日志仍可用；Ruff/格式/pip check、前端类型/2 个测试/构建、真实首页/API 文档/健康/404/代理/日志检查通过。M1 六项全部完成；后续进入 M2。

M1 集成记录（2026-10-11）：经用户授权，`feature/m1-06-runtime-foundation` 已通过 `git merge --ff-only` 合并至本地 `main`，无冲突且代码树不变。合并后 Ruff/格式、37 个非 PostgreSQL 后端测试、前端类型/2 个测试和文档/健康 HTTP 检查通过。本轮未重跑数据库升降级；先前完整 38 项验收保留为历史证据。本地 main 尚未推送；M2-01 改从本地 main 创建功能分支。

M1 同步/清理记录（2026-10-11）：后续已获用户明确授权，main 推送 GitHub 并核验 SHA 一致后，以 `git branch -d` 删除三个已合并本地 M1 功能分支；远程功能分支保留，代码与历史不变。Ruff、37 个非 PostgreSQL 测试通过。本轮交接记录同步 main；下一任务从 main 新建 M2-01 分支。

## Milestone 2：股票基础信息与行情采集

- DONE M2-01 定义 `MarketDataProvider` 契约和 `AkShareProvider`。
  - 验收：外部字段不泄漏到服务层；使用 mock 的契约测试覆盖成功、空结果、超时和字段漂移。
  - 验收结果（2026-10-11）：已实现不可变 DTO/批次元数据、SH/SZ 基础信息与不复权日线适配、手转股/Decimal/UTC 时间、配置化总超时与 SDK 子进程回收，复用日志/错误。AKShare 1.19.1 可选 extra 安装与签名核验通过；固定 fixture/mock/真实子进程离线测试和后端回归共 90 passed、1 deselected（PostgreSQL）。Ruff/格式/pip check 通过；无表或 migration 变化，未重跑数据库/前端测试，未联网采集真实行情。边界见 docs/MARKET_DATA_PROVIDER.md 与 ADR-012。
- DONE M2-02 实现股票代码、日期、OHLCV、单位和异常值校验。
  - 验收：SH/SZ 正常及非法代码、空/异常行情和字段换算测试通过。
  - 验收结果（2026-10-11）：新增独立纯函数 Validator，覆盖显式 SH/SZ 支持代码段、日期区间/重复/乱序、空与非有限值、OHLC、负量、Decimal/BigInt 精确存储范围、元数据/单位/UTC 与显式交易日历；不重复手转股、不舍入、不修改输入。新增 143 项固定模拟测试，完整非 PostgreSQL 后端回归 233 passed、1 deselected；Ruff/格式/pip check 与独立导入检查通过。无新依赖、模型或 migration 变化，未运行本轮数据库升降级和前端测试。未提供日历时不声明完整交易日验收；详见 docs/MARKET_DATA_VALIDATOR.md、ADR-013。
- DONE M2-03 实现股票基础信息同步与搜索持久化。
  - 验收：重复同步幂等；名称/代码搜索和状态字段测试通过。
  - 验收结果（2026-10-11）：StockService -> StockRepository -> PostgreSQL 已实现，复用 Provider/Validator；UPSERT 保护 unknown/None，缺席不删，重复不改写，RETURNING 精确统计变更。搜索字面匹配代码/名称，稳定分页及 REPEATABLE READ 一致快照。新增 16 单元/6 PostgreSQL 集成测试；非 PostgreSQL 249 passed、7 deselected，新空隔离双库完整回归 256 passed 无 skip，含 migration 升降级。Ruff/格式/pip check 通过；无 Schema、业务 API、CLI 或前端变更。开发库与卷保留，详见 docs/STOCK_PERSISTENCE.md。
- DONE M2-04 实现日线采集、日期区间补采和 UPSERT。
  - 验收：重复采集不新增重复行；日期过滤、部分失败和事务边界测试通过。
  - 验收结果（2026-10-11）：DailyPriceService/Repository 复用 Provider/Validator，闭区间补采、复合主键 UPSERT、数值/来源相同不改写、每股票独立事务；整股预校验与 500 行分块写入原子回滚，跨股已知失败继续并保留成果，提交后返回安全收据/部分失败摘要。新增 19 单元/12 PostgreSQL 测试；268 passed、19 deselected，全新三隔离库完整 287 passed 无 skip，含并发幂等、502 行回滚/手动恢复及 migration 升降级。Ruff/格式/pip check 通过，无新依赖/Schema/CLI/API/任务状态；开发库和卷保留，详见 docs/DAILY_PRICE_PERSISTENCE.md、ADR-015。
- DONE M2-05 实现受控本地采集 CLI 与同步任务记录。
  - 验收：任务状态、错误摘要、失败重试和断点恢复测试通过；不提供匿名公网触发入口。
  - 验收结果（2026-10-11）：本地 stocks/daily/jobs/resume CLI，复用 Provider/Validator/Service 与 DataSyncJob；每股独立任务、工作项计数与空响应标记、提交后实际 checkpoint、安全错误码、有界重试、全局协作锁/活动防重、原范围幂等恢复。新增 26 单元/10 PostgreSQL 测试，294 passed、29 deselected；全新四隔离库完整 323 passed 无 skip，包含真实 SIGTERM/SIGKILL、提交后崩溃、离线 SDK CLI、partial/failed 与 migration 升降级。Ruff/格式/pip check 通过，无新依赖/Schema/API/前端/调度器；开发库和原卷保留。详见 docs/COLLECTION_CLI.md、ADR-016。M2 五项全部完成，下一任务 M3-01。

M2 集成/同步记录（2026-10-11）：经用户授权，`feature/m2-05-collection-cli` 已快进合并本地 main，M2 五个功能提交全部推送 GitHub；代码交付 `ca50c94` 已核验远程一致。合并后 Ruff/格式及 294 个非 PostgreSQL 测试通过（29 deselected），未重跑数据库/前端验收，原完整 323 项证据保留。功能分支未删除；下一任务从同步后的 main 创建 M3-01 分支。

## Milestone 3：历史行情 API 和 K 线展示

- DONE M3-01 实现股票列表、详情和行情查询 API。
  - 验收：Pydantic 契约、分页/上限、代码和日期校验、来源与更新时间均有 API 测试。
  - 验收结果（2026-10-11）：三项 GET 只读 API，复用 Service/Repository/Validator，稳定分页、闭区间升序/limit/has_more、精确 Decimal 字符串、CNY/股/不复权、逐行来源/UTC 时间；股票无元数据列，明确 null。新增 28 单元与 5 PostgreSQL API 集成测试，全新五隔离库完整 356 passed 无 skip，含既有 migration 升降级；Ruff/格式/pip check 与真实 HTTP/代理通过。无新依赖/Schema/前端/采集/调度变化，开发库与原卷保留。首轮既有采集锁冲突 1 failed/355 passed，未改采集代码，独立新库复跑全部通过；潜在竞态记录在交接文档。详见 docs/STOCK_QUERY_API.md、ADR-017。
- DONE M3-02 实现统一前端 API 客户端、路由和页面框架。
  - 验收：请求错误统一处理，不含密钥，类型检查通过。
  - 验收结果（2026-10-12）：同源 Axios/类型契约/响应结构校验、统一安全错误与 request_id、请求取消和晚到隔离、搜索/详情路由及共享状态组件；前端类型、13 项测试和生产构建通过，安装审计 0 漏洞。无后端/Schema 变化；详见 docs/FRONTEND_MARKET.md。
- DONE M3-03 实现 Dashboard、StockSearch 和 StockDetail 基础视图。
  - 验收：搜索到详情主路径可用，Loading/Empty/Error 状态均可复现。
  - 验收结果（2026-10-12）：概览本地计数、URL 关键词/分页/返回、详情基础信息/日期过滤/逐行来源时间、1000 条截断提示、空/失败/重试已实现；类型检查、21 项前端测试与生产构建通过，无后端/Schema 变更。
- DONE M3-04 实现 K 线和成交量图。
  - 验收：日期排序、缩放和来源/更新时间展示正确；核心查询链路测试通过。
  - 验收结果（2026-10-12）：模块化 ECharts SVG 日 K 线/成交量零基线、双图缩放、ResizeObserver/dispose、精确 tooltip/明细和逐行/汇总来源时间；类型/25 项测试/宿主与容器构建通过，Chromium 桌面/390px 搜索到详情、鼠标缩放/空/错/重试通过；新隔离库 20 条模拟行情经真实 API 到浏览器/SVG 链路通过。开发库四表仍空、原卷与三服务保留；后端离线 322 passed/34 deselected，Ruff/格式通过，未重跑完整 PostgreSQL 升降级。保留约 572 KB 图表 chunk 警告；详见前端专题/交接/ADR-018。M3 全部完成，下一任务 M4-01。

M3 集成/同步记录（2026-10-12）：用户明确授权后，四项 M3 提交已快进合并本地 main 并正常推送 GitHub；远程代码 SHA `beeafa6354898dce8c08f37d5bfe5534e82fdbd9` 与本地一致。合并后前端类型/25 项测试、后端离线 322 passed/34 deselected、Ruff/格式通过；待推送历史 67 个 blob 敏感信息检查通过。未改代码树、未重跑数据库升降级/浏览器/构建，既有验收证据保留。同步记录另提交并推送，功能分支保留；下一任务从同步后的 main 创建 M4-01 分支。

## Milestone 4：均线分析与自动更新

- DONE M4-01 实现 MA5、MA20、MA60 纯计算模块。
  - 验收：正常、窗口边界、历史不足、乱序、非法输入和无未来数据测试通过。
  - 验收结果（2026-10-12）：纯 Decimal 模块、固定版本/四位 HALF_UP、分组排序/无未来数据，11 项固定模拟测试通过；无依赖和 Schema 变化，见 docs/MOVING_AVERAGES.md。
- DONE M4-02 持久化带版本的技术指标并提供查询 API。
  - 验收：受影响日期可重算，查询契约和幂等性测试通过。
  - 验收结果（2026-10-12）：指标/行情同事务、股票行锁、全历史受影响重算/幂等，均线和状态只读 API；六个全新隔离库完整后端 370 passed，含 migration/回滚/Decimal/null/错误脱敏，无 Schema 变化。
- DONE M4-03 在 StockDetail 展示均线并实现 DataStatus 页面。
  - 验收：图例/空值/来源/版本/任务错误状态可见，类型和组件测试通过。
  - 验收结果（2026-10-12）：MA5/20/60 后端值按日期叠加，null 断线、原始 Decimal/版本/来源/计算时间，数据状态只读页；类型/31 项测试/构建及 Chromium 桌面/390px、均线/空错重试/状态页通过。
- DONE M4-04 实现独立盘后调度进程。
  - 验收：Asia/Shanghai 可配置调度、交易日历、防重、失败重试和部分成功测试通过；API 多 Worker 不重复调度。
  - 验收结果（2026-10-12）：独立上海盘后调度、显式来源/覆盖日历、持久成功跳过、双锁/有界重试/单股部分失败与增量重叠水位；真实调度 CLI 子进程重启防重通过，完整后端 383 passed 无 skip，详见 docs/SCHEDULER.md。
- DONE M4-05 完成手工增量/补采操作说明。
  - 验收：本地 CLI 命令、权限边界、预期输出和故障恢复经过演练。

  - 验收结果（2026-10-12）：操作手册覆盖本机环境/权限/增量/补采/本地重算/原任务恢复/调度退出码；真实离线 CLI 子进程与本地重算已演练，383 项完整后端及 31 项前端、浏览器全链路通过；脚本创建新隔离库，开发库原四表仍空。M4 五项全部完成，本轮停止，下一任务 M5-01。

M4 集成/同步记录（2026-10-12）：用户明确授权后，五项 M4 提交已快进合并本地 main 并正常推送 origin/main；远程代码 SHA 30730a31b231ab7ec224d9896c170e9916c9bd76 已核验一致。合并后离线后端 341 passed/42 deselected、前端类型/31 项测试、Ruff/格式通过；五项历史 188 个 blob 敏感信息/大文件检查通过。本轮未重跑数据库升降级/浏览器/构建，原验收证据保留。功能分支保留；真实行情未初始化、常驻调度未启动，不能将开发验收视为真实数据运行完成。同步记录另提交并同步。

## Milestone 5：测试、文档和 v0.1.0 验收

- DONE M5-01 完成后端、前端、migration 和端到端核心链路测试。
  - 验收：规划中的十类测试有结果；无未说明的失败或跳过。
  - 验收结果（2026-10-12）：六个新隔离库后端 388 passed 无 skip，前端类型/31 项测试/构建、模拟边界及真实行情桌面/手机浏览器通过；十类矩阵见 docs/M5_ACCEPTANCE.md。
- DONE M5-02 验证全新 Linux 环境的 Docker Compose 部署。
  - 验收：从空环境按 README 启动、迁移、采集固定样例并查询展示成功。
  - 验收结果（2026-10-12）：独立 Ubuntu24.04.5 VM/内核/Docker，零镜像/容器/卷，按 README 预构建开发镜像路径部署；迁移无差异，采集前四表0行，真实采集后5223/732/732/6行，独立调度4项成功、API/真实桌面/手机浏览器通过。TCG健康预算覆盖保留原HTTP探测，最终三服务healthy。
- DONE M5-03 完成安全、依赖、数据口径和授权复核。
  - 验收：无已知密钥泄漏，高风险依赖有处置，页面免责声明和数据来源清楚。
  - 验收结果（2026-10-12）：Python 依赖 constraints 与前端 lock；pip-audit 无已知漏洞，开启 TLS 验证的 npm audit 0 漏洞；来源/单位/声明/loopback 与私有凭据扫描通过，公开再分发许可未取得，M6 仍需授权。
- DONE M5-04 验证 PostgreSQL 备份与恢复。
  - 验收：从备份恢复到独立实例并核对表、行数和核心查询。
  - 验收结果（2026-10-12）：GPG AES-256 归档恢复到新 PostgreSQL 实例，四表内容哈希及行数、revision、规范化约束/索引一致；恢复 API 五项查询通过，原库和卷保留，未落盘明文归档。
- DONE M5-05 完成 v0.1.0 发布候选验收。
  - 验收：文档与实现一致，CHANGELOG 完整，经用户确认后再创建标签/Release。
  - 验收结果（2026-10-12）：M5 五项全部通过，v0.1.0 RC 文档与真实运行证据一致；本地功能分支提交；随后经用户明确授权，于2026-10-12快进合并main并推送origin/main（功能交付c303d95），保留功能分支；未打标签/发布，M6 未启动。

## M5 后数据源维护（2026-10-12）

- DONE 排查东方财富可用性并提供替代方案：直连/环境代理 HTTP200，原 Provider/Validator 沪深两样本各183条通过，腾讯对照通过；新增只读诊断脚本与 docs/MARKET_DATA_DIAGNOSTICS.md。此前网络失败不可复现，根因未确定，不宣称永久修复。M6未启动。

## M5 后页面体验维护（2026-10-12）

- DONE 股票搜索/详情信息可读性：合并缺失基础资料提示，保留已确认状态，中文来源与均线说明，技术细节按需展开；仅前端，不变更数据口径与M6范围。验收：类型检查、35项组件/API/图表测试、生产构建通过；模拟边界与真实183条行情桌面/390px手机浏览器通过，无浏览器异常。

## M5 后来源控制与教程（2026-10-12）

- DONE 网页来源设置与自动备用：三种策略、管理口令及同源限制、原子持久化/revision、逐股动态读取、真实来源与安全备用日志；不触发HTTP采集。后端399passed，前端38passed/类型/构建，真实网页三模式/刷新/手机通过，常驻容器真实备用腾讯两只各183条通过。
- DONE 首页使用教程入口及独立教程页：搜索/K线/均线/来源/更新步骤与4只覆盖范围一致，手机及链接验收通过。M6未启动。

## Milestone 6：Linux 公网部署（2026-10-12 已授权实施；暂无公网资源）

- DONE M6-01 形成 VPS 规格、区域、成本和域名建议。
  - 验收：基于已测负载和数据量，不在 M5 前采购。
  - 验收结果（2026-10-12）：用户确认2–10名受邀用户、约100股、先评估成本；只读实测库8.82MiB/4股732条、240次查询零失败、10并发p95 192–211ms、逻辑dump 92,383bytes/0.347s。报告包含100股/多年存储模型、串行采集与备用延迟风险、2核4GiB/80GiB待验证候选、官方费用参照、地域/域名及目标环境门禁；ADR-022为Proposed。复现脚本运行、Ruff/格式和文档检查通过；未扩大名单、重采、变更生产配置、采购或部署。详见docs/M6_CAPACITY_ASSESSMENT.md。
- DONE M6-02 实现生产 Compose、反向代理和 HTTPS。
  - 验收：仅开放必要端口，PostgreSQL 5432 不暴露公网，密钥不进 Git。
  - 验收结果：独立生产镜像/Compose，新卷/loopback18080/18443；Caddy静态资源、HTTPS/SPA/同源API、双层禁写，无DB/API发布端口。严格CA/HTTP跳转验证11项通过；实际公网证书/目标主机部署留M6-04。详见docs/M6_ACCEPTANCE.md。
- DONE M6-03 实现生产访问控制、监控和备份策略。
  - 验收：最小权限、恢复演练、日志轮转和告警经过验证。
  - 验收结果：逐人认证/撤销、四类数据库权限、日志轮转脱敏、行情/容量/备份/TLS监控及HTTPS回调、GPG/SSH/远端哈希、独立空库恢复与同schema回滚已本地验证。100股99成功/1失败保留；399后端/39前端/18运维测试通过。异地故障隔离与公网运维须在M6-04复验。
- TODO M6-04 经用户明确授权后部署。
  - 验收：部署记录、回滚方案和公网验收完成。
  - 当前阻碍：用户确认暂无服务器、域名、异地备份目标；行情展示授权/实际告警接收人亦未提供。已完成本地发布与故障回滚演练，但未声称公网验收或整个M6完成。不采购、不push。

### M6 后续探索：Cloudflare Tunnel（2026-10-12）

- DONE 阶段A：只读检查现有Ubuntu/WSL2、Docker、两套容器/端口、Caddy/TLS/认证路由、数据库隔离、Git与出站网络；不改原部署配置。
- DONE 阶段B程序验证与清理：官方临时二进制SHA-256、独立静态Quick Tunnel QUIC连接、严格HTTPS/本机浏览器200、负向路径404；测试PID/HTTP/metrics已关闭，旧URL530，原容器/部署哈希不变。详见docs/M6_TUNNEL_FEASIBILITY_20261012.md。
- DONE 阶段B外网人工验证：2026-10-12 13:12重新开启隔离窗口，用户反馈手机访问成功、内容一致、无证书警告。13:14提前停止，进程退出0、测试端口关闭、公网返回530且无测试正文；首次未反馈记录保留。仅隔离连通性通过，M6-04及原失败项不变。
- DONE 限时业务公网试用启动与程序验证：用户明确授权；独立Quick Tunnel接原Caddy HTTPS/邀请认证/只读入口，23项公网门禁及严格TLS浏览器真实搜索/K线/手机布局通过，原服务不改。14:23:45到期，见docs/M6_BUSINESS_TRIAL_20261012.md。
- DONE 业务试用手机外网反馈：用户13:28反馈登录成功、搜索和K线正常，证据external-feedback.json。
- IN PROGRESS 业务试用窗口清理核验：带认证窗口已到期，state process_stopped=true；进程/端口及旧公网失效复核进行中，原13容器及配置不变。当前另有已明确授权的独立匿名窗口，旧认证窗口外部探测分别遇URLError/DNS错误，不能伪记530。
- TODO 长期业务映射：账号/固定域名/Access、可信代理IP审计、WSL持续运行、数据用途许可和真实异地恢复仍需完成；M6-04及原失败项状态不变。

### 第一版交付与根目录启动脚本（2026-10-12）

- DONE 本机启动脚本：stockinsight.sh start/public/status/public-stop，默认8小时匿名只读方案，本地19项检查通过，官方工具持久保存Git忽略目录，原容器/数据库不改。
- DONE 匿名公网实际验证：用户补充明确授权后审批通过，19项公网门禁及严格TLS桌面/手机浏览器真实业务通过，手机反馈“正常”。本轮至北京时间23:37:08；到期清理尚待实际执行。
- DONE 首版合并推送：用户接受当前已知限制并明确授权；功能首版快进合并main至ad38557并正常推送origin/main，远端SHA实际核验一致。无force/tag/Release，原失败项不改判。

## Milestone 7：财务分析（预留）

- TODO M7-01 经需求与数据授权评审后设计财务数据模型。
  - 验收：明确报告期、公告日、获取日、版本及防未来信息泄漏规则。
- TODO M7-02 实现获批的财报与估值功能。
  - 验收：另行定义，不影响 v0.1.0 边界。

## Milestone 8：自选股和模拟组合（预留）

- TODO M8-01 评审用户体系、自选股和模拟组合范围。
  - 验收：隐私、认证、成本口径和公司行动规则获批。
- TODO M8-02 实现获批范围。
  - 验收：另行定义；不连接真实券商、不执行交易。

## Milestone 9：风险分析（预留）

- TODO M9-01 评审风险指标、基准、时间区间与免责声明。
  - 验收：方法可复核，历史统计与预测严格区分。
- TODO M9-02 实现获批风险分析。
  - 验收：另行定义，覆盖偏差、缺失值和边界测试。

## Milestone 10：策略回测与研究报告（预留）

- TODO M10-01 评审回测和报告范围。
  - 验收：手续费、滑点、公司行动、幸存者偏差与未来函数处理获批。
- TODO M10-02 实现获批范围。
  - 验收：另行定义；输出不得包装为保证收益的建议。

### 剩余问题修复跟踪（2026-10-12）

- DONE 000016.SZ原因确认及修复候选：官方9月28日公告确认9月4日起停牌；有限公告区间、真实上游158根至9月3日日线、后端407测试和运维22测试通过。调度与监控共用登记器，旧失败任务不改，不伪造停牌日行情。候选镜像及Compose校验完成，见docs/M6_REMEDIATION_20261012.md。
- DONE 停牌修复应用到既有环境：解释后用户明确“可以执行更新”；仅scheduler/monitor获准重建，实际补采158根至9月3日，100股有历史/日线与指标各18,264行。旧failed保留；重复tick跳过100且101任务不变；原HTTPS11项与匿名公网新增数据通过。首次更新前逐字段快照缺证据如实记录，真实异地/维护失败不改判。
- TODO 维护失败排查（用户接受现状，暂缓至使用有影响时）：新匿名代理15分钟10读者/3次热加载26,037请求/1连接异常、p95 16.81ms，严格零失败未通过；90秒/28次密集热加载复现3次RemoteDisconnected，时间均贴近reload；已补异常时间/类型诊断，需评审维护窗口或滚动部署方案。原51失败及完整混合维护验收不改判。
- BLOCKED 真实异地备份：缺独立故障域目标及可信访问配置，同机接收器不能替代。
- BLOCKED WSL断电/休眠/重启恢复及长期可用性：需用户安排窗口和Windows电源策略，不能擅自中断现有服务。
- TODO 当前8小时窗口到期清理核验：23:37:08后检查自有Tunnel/临时代理退出及旧URL不再返回业务；不得预记成功。
