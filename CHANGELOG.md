# Changelog

本项目遵循 [Keep a Changelog](https://keepachangelog.com/zh-CN/1.1.0/) 的结构，并计划采用语义化版本。

## [Unreleased]

### Added

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

### Known limitations

- Milestone 1 正在进行；后端健康接口可运行，但尚无股票业务 API、业务模型或数据库表。
- 当前尚未创建或验证项目 Docker Compose 服务、PostgreSQL 容器和应用运行链路。
- Alembic 已初始化但 revision 数为 0；首个业务 migration 属于 M1-04。
