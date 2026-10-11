# Changelog

本项目遵循 [Keep a Changelog](https://keepachangelog.com/zh-CN/1.1.0/) 的结构，并计划采用语义化版本。

## [Unreleased]

### Added

- M3-01：新增股票列表/搜索、详情与显式区间日线 GET API，稳定分页/日期排序/上限、安全错误、只读事务与并发快照；复用既有服务和持久化层，无新依赖或 Schema。
- 新增 28 单元与 5 PostgreSQL API 测试，完整 356 passed；日线保留来源/UTC 时间/不复权/单位和 Decimal 字符串，股票缺失来源/时间明确 null。详见 docs/STOCK_QUERY_API.md、ADR-017。

- M2-05：新增受控本地 stocks/daily/jobs/resume CLI、每股持久任务与安全错误摘要、Provider 有界退避、协作采集锁/活动防重、提交后 checkpoint 与原范围幂等恢复。
- 新增 26 单元和 10 PostgreSQL 测试，覆盖全/部分失败、重复运行、真实进程中断与提交后恢复；复用已有服务、配置和模型，无 Schema、业务 API 或前端变化。详见 docs/COLLECTION_CLI.md、ADR-016。

- M2-04：新增日线闭区间采集/补采服务与 PostgreSQL 幂等 UPSERT，来源/UTC 时间/不复权逐行保存，单位和精度复用 Validator；同值不重写，实际变更使用 RETURNING 计数。
- 每股票独立事务与整股分块回滚、跨股票安全失败摘要/继续采集、手动幂等恢复；新增 19 单元与 12 真实 PostgreSQL 测试，完整 287 passed。无新依赖、Schema、CLI、API 或任务状态变化。

- M2-03：新增股票基础信息同步服务和 PostgreSQL Repository，复用 Provider/Validator；幂等 UPSERT 保留已知状态/上市日期，快照缺席不删，提交后返回来源/时间与处理/实际变更计数。
- 新增代码/名称字面搜索、稳定分页及同快照 total/items；固定模拟 Provider 与真实隔离数据库覆盖事务回滚、并发幂等和搜索一致性，无业务 API/CLI 或 Schema 变化。

- M2-02：新增纯函数 Validator，复用 Provider DTO 校验 SH/SZ 代码、日期区间/重复、OHLCV、单位/口径、来源与 UTC 时间，排序且保留原始输入。
- 新增精确 Decimal/BigInt 存储边界、显式交易日历参数与不回显原始值的错误诊断；固定模拟值与 Provider fixture 组合测试覆盖边界，金额不舍入、成交量不重复换算。

- M2-01：定义可替换 MarketDataProvider、不可变基础信息/日线/批次契约与 AkShareProvider，隔离外部字段，明确 SH/SZ、不复权、UTC 时间和 CNY/股单位。
- 新增 AKShare 1.19.1 可选 market-data extra、环境可配置总超时与单次 SDK 子进程隔离，复用安全日志及公开错误契约；新增明确标记的模拟 fixture、mock Provider 和离线子进程测试。
- 新增 Provider 字段映射、空结果/漂移/超时边界及真实上游尚未验收的专题文档。

- M1-06：通过现有 Pydantic 建立环境白名单配置及开发/测试数据库隔离，兼容无密码 URL 与 libpq PG*，配置加载不连接/迁移数据库。
- 新增服务端请求关联 ID、Pydantic 统一错误响应、HTTP/校验/应用/未知异常处理和安全 JSON 日志；禁用 Uvicorn 原始 access log。
- 新增共享应用/客户端/一次性数据库 fixture 与配置、错误、脱敏、并发关联 ID 和日志输出失败测试。

- 初始化 StockInsight 项目目录和本地 Git 仓库。
- 新增项目规划、开发协作规则、全阶段任务清单和项目说明。
- 新增系统架构、数据采集、数据库及 API 草案。
- 新增后端、前端、脚本、文档和基础设施目录骨架。
- 新增安全的忽略规则与环境变量示例。
- 新增会话交接文档，记录可核验的项目、测试、Git、migration 和下一任务状态。
- 新增技术决策记录，说明首版核心技术与产品边界的选择依据。
- 新增本地及生产部署规划、备份恢复、发布和回滚要求。
- 补充会话首尾检查、架构一致性检查及 GitHub 管理规则。
- 新增项目 `.nvmrc` 和可重复执行的环境检查脚本。
- 通过 NVM 并行配置 Node.js 22.23.1，并建立仓库内 Python 3.12 虚拟环境；保留系统 Node/Python 以避免影响其他项目。
- 安装并验证 Docker Engine 29.1.3、Docker Compose 2.40.3 和 PostgreSQL 客户端 16.15；在当前 Ubuntu WSL 中启用 systemd 并验证 Docker daemon 可达。
- 使用项目所有者提供的 GitHub 私有仓库完成 `main` 首次同步，并记录远程跟踪状态。
- 初始化 Python 3.12 后端工程及 FastAPI 应用工厂，新增只表示 API 进程存活的 `GET /api/v1/health`。
- 新增 Pydantic 健康响应契约、SQLAlchemy 2 延迟 Engine/Session 基础配置和空 Alembic migration 环境。
- 配置 Pytest、Ruff 和后端开发依赖，新增健康接口状态码、响应结构、版本及敏感信息泄漏测试。
- 初始化 Vue 3、TypeScript、Vite 和 Vue Router 前端基础工程，新增首页应用壳、404 路由及移动端基础样式。
- 新增 Vitest 与 Vue Test Utils 组件/路由测试、类型检查、生产构建、Preview 和可复现 `npm ci` 入口。
- 固定经审计的前端构建工具版本并生成 `package-lock.json`；当前 npm 审计为 0 个已知漏洞。
- 新增四张 SQLAlchemy 2 模型及 `0001_initial_schema` Alembic migration，包含主外键、OHLC/单位/复权约束和查询索引。
- 补齐同步任务目标范围、股票工作项计数、恢复游标和同范围活动任务部分唯一索引；使用 psycopg 3 连接 PostgreSQL。
- 新增 metadata 和真实 PostgreSQL migration 验收，覆盖空库升级、约束、防重、降级/再升级及 ORM 无差异检查。
- 新增 `compose.yaml`、Python/Node 开发 Dockerfile 和构建上下文忽略规则；提供本机绑定的 PostgreSQL 16、API 与 Vite 三服务。
- 新增随机本地 `.env` 初始化入口，设置 0600 权限并拒绝覆盖已有文件；数据库连接密码通过 libpq 环境变量传入。
- 新增 Vite `/api` 开发代理，保留原生开发默认目标；开发镜像采用非 root 应用用户和只读源码挂载。
- 完成本地 Compose 构建、健康、网络数据库连接、显式 migration、HTTP、隔离库全后端回归、容器前端测试及持久卷停止/恢复验收。

### Known limitations

- Milestone 1、Milestone 2 与 M3-01 已完成；本地采集 CLI 和查询 API 经模拟来源/真实隔离库验收，真实上游稳定性与行情页面尚未验收/实现。
- 全量首轮既有采集测试出现一次 advisory lock 冲突；新隔离库复跑通过，连接物理关闭与锁释放潜在竞态待后续调查。
- 本地 Compose 已验收；生产部署、全新 Linux 环境验证和备份恢复仍待完成。
- 当前唯一 Alembic head 为 `0001_initial_schema`，本地持久开发库已升级；不包含真实或模拟行情数据。
- 当前 daemon 直接拉取 Docker Hub 超时；已通过用户态工具经既有代理下载官方镜像并导入，未变更系统 daemon 配置。后端依赖和基础镜像 digest 尚未完全锁定。

### 2026-10-12 M3-02

- 建立同源 Axios 客户端、股票/日线精确字符串契约与响应校验、统一安全错误/请求编号、可取消请求状态和搜索/详情路由框架。

### 2026-10-12 M3-03

- 增加本地股票概览、可保留搜索条件的分页目录、基础信息和历史日线详情；统一加载/空/错误重试、日期过滤与来源时间展示。

### 2026-10-12 M3-04

- 增加按日期排序的 SVG 日 K 线和零基线成交量图、联动滑块/滚动缩放、尺寸更新与资源销毁。
- 保留精确价格/成交额明细与提示，展示来源/上海获取时间和区间截断提示，修正窄屏 Grid 溢出与未提交关键词影响分页。
- 增加真实 ECharts SVG 与可复现 Chromium 冒烟测试；完成 20 条模拟日线在独立 PostgreSQL/API 到浏览器的验证。M3 全部完成，M4 待启动。

- 2026-10-12 M4-01：独立 Decimal MA5/20/60 计算、版本和边界测试。
