# StockInsight 开发任务

状态枚举：`TODO`、`IN PROGRESS`、`DONE`、`BLOCKED`。只有实现完成、验收命令通过且文档同步后才能标记 `DONE`。

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
- TODO M1-06 建立统一配置、日志、异常和测试 fixture。
  - 验收：开发/测试配置隔离，日志脱敏，错误模型有测试。

## Milestone 2：股票基础信息与行情采集

- TODO M2-01 定义 `MarketDataProvider` 契约和 `AkShareProvider`。
  - 验收：外部字段不泄漏到服务层；使用 mock 的契约测试覆盖成功、空结果、超时和字段漂移。
- TODO M2-02 实现股票代码、日期、OHLCV、单位和异常值校验。
  - 验收：SH/SZ 正常及非法代码、空/异常行情和字段换算测试通过。
- TODO M2-03 实现股票基础信息同步与搜索持久化。
  - 验收：重复同步幂等；名称/代码搜索和状态字段测试通过。
- TODO M2-04 实现日线采集、日期区间补采和 UPSERT。
  - 验收：重复采集不新增重复行；日期过滤、部分失败和事务边界测试通过。
- TODO M2-05 实现受控本地采集 CLI 与同步任务记录。
  - 验收：任务状态、错误摘要、失败重试和断点恢复测试通过；不提供匿名公网触发入口。

## Milestone 3：历史行情 API 和 K 线展示

- TODO M3-01 实现股票列表、详情和行情查询 API。
  - 验收：Pydantic 契约、分页/上限、代码和日期校验、来源与更新时间均有 API 测试。
- TODO M3-02 实现统一前端 API 客户端、路由和页面框架。
  - 验收：请求错误统一处理，不含密钥，类型检查通过。
- TODO M3-03 实现 Dashboard、StockSearch 和 StockDetail 基础视图。
  - 验收：搜索到详情主路径可用，Loading/Empty/Error 状态均可复现。
- TODO M3-04 实现 K 线和成交量图。
  - 验收：日期排序、缩放和来源/更新时间展示正确；核心查询链路测试通过。

## Milestone 4：均线分析与自动更新

- TODO M4-01 实现 MA5、MA20、MA60 纯计算模块。
  - 验收：正常、窗口边界、历史不足、乱序、非法输入和无未来数据测试通过。
- TODO M4-02 持久化带版本的技术指标并提供查询 API。
  - 验收：受影响日期可重算，查询契约和幂等性测试通过。
- TODO M4-03 在 StockDetail 展示均线并实现 DataStatus 页面。
  - 验收：图例/空值/来源/版本/任务错误状态可见，类型和组件测试通过。
- TODO M4-04 实现独立盘后调度进程。
  - 验收：Asia/Shanghai 可配置调度、交易日历、防重、失败重试和部分成功测试通过；API 多 Worker 不重复调度。
- TODO M4-05 完成手工增量/补采操作说明。
  - 验收：本地 CLI 命令、权限边界、预期输出和故障恢复经过演练。

## Milestone 5：测试、文档和 v0.1.0 验收

- TODO M5-01 完成后端、前端、migration 和端到端核心链路测试。
  - 验收：规划中的十类测试有结果；无未说明的失败或跳过。
- TODO M5-02 验证全新 Linux 环境的 Docker Compose 部署。
  - 验收：从空环境按 README 启动、迁移、采集固定样例并查询展示成功。
- TODO M5-03 完成安全、依赖、数据口径和授权复核。
  - 验收：无已知密钥泄漏，高风险依赖有处置，页面免责声明和数据来源清楚。
- TODO M5-04 验证 PostgreSQL 备份与恢复。
  - 验收：从备份恢复到独立实例并核对表、行数和核心查询。
- TODO M5-05 完成 v0.1.0 发布候选验收。
  - 验收：文档与实现一致，CHANGELOG 完整，经用户确认后再创建标签/Release。

## Milestone 6：Linux 公网部署（须用户决定启动）

- TODO M6-01 形成 VPS 规格、区域、成本和域名建议。
  - 验收：基于已测负载和数据量，不在 M5 前采购。
- TODO M6-02 实现生产 Compose、反向代理和 HTTPS。
  - 验收：仅开放必要端口，PostgreSQL 5432 不暴露公网，密钥不进 Git。
- TODO M6-03 实现生产访问控制、监控和备份策略。
  - 验收：最小权限、恢复演练、日志轮转和告警经过验证。
- TODO M6-04 经用户明确授权后部署。
  - 验收：部署记录、回滚方案和公网验收完成。

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
