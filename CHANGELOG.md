# Changelog

本项目遵循 [Keep a Changelog](https://keepachangelog.com/zh-CN/1.1.0/) 的结构，并计划采用语义化版本。

## [Unreleased]

### Added

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

- Milestone 1 与 M2-01 至 M2-03 已完成；基础信息持久化经模拟来源/真实隔离数据库验收，真实上游、日线持久化、业务 API 与行情页面尚未验收或实现。
- 本地 Compose 已验收；生产部署、全新 Linux 环境验证和备份恢复仍待完成。
- 当前唯一 Alembic head 为 `0001_initial_schema`，本地持久开发库已升级；不包含真实或模拟行情数据。
- 当前 daemon 直接拉取 Docker Hub 超时；已通过用户态工具经既有代理下载官方镜像并导入，未变更系统 daemon 配置。后端依赖和基础镜像 digest 尚未完全锁定。
