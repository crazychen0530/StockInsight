# StockInsight 会话交接

> 更新时间：2026-10-10（Asia/Shanghai）
>
> 本文件记录可核验的当前状态。新会话开始时必须结合 Git、任务清单和实际环境重新确认；不得把规划内容当作已实现功能。

## 1. 当前版本与里程碑

- 目标版本：`v0.1.0`
- 当前完成阶段：Milestone 0（项目初始化与长期文档）
- 当前完成任务：Milestone 1 的 M1-01（环境前置配置）
- 下一任务：Milestone 1 的 M1-02（后端基础工程与健康检查）
- 当前交付性质：开发环境已经验收；尚无可运行的股票业务功能

## 2. 当前 Git 状态

- 当前分支：`main`
- 上游分支：`origin/main`
- 本次会话开始时最近提交：`97a83a0 docs: record GitHub initial synchronization`
- 当前环境配置提交：`chore: configure project development environment`
- 远程仓库：`git@github.com:crazychen0530/StockInsight.git`
- GitHub 推送：此前 `main` 已同步；本次提交尚未推送

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

尚未实现 FastAPI、Vue、数据库表、Alembic migration、行情采集、指标计算、定时任务或页面展示。

## 4. 正在开发的功能

当前没有正在开发的功能。M1-01 已完成实际验收，M1-02 尚未开始。

## 5. 未完成任务

下一阶段优先任务来自 `TASKS.md`：

1. M1-02：初始化 FastAPI、SQLAlchemy 2、Pydantic、Alembic、Pytest 和 Ruff 工程，实现健康检查。
2. M1-03：初始化 Vue 3、TypeScript 和 Vite 工程。
3. M1-04：确认 `data_sync_jobs` 的范围、计数和断点字段后，创建首个 migration。
4. M1-05/M1-06：建立本地 Compose、配置、日志、统一错误和测试 fixture。

不得跳过 M1 直接实现实时行情、AI 预测、自动交易或其他后续范围。

## 6. 最近一次实际测试及结果

本次环境配置实际验证结果：

- Ubuntu 24.04.3 LTS on WSL2、Python 3.12.3：通过。
- NVM 0.40.6 与 Node.js 22.23.1 安装/项目选择：通过。
- 系统 Node.js 保持 18.19.1，NVM `default` 别名未保留：通过隔离检查。
- `.venv` 使用 Python 3.12.3、pip 26.2.1，`pip check`：通过，无损坏依赖。
- `.venv` 命中 `.gitignore`：通过。
- Docker CLI 29.1.3、Compose 2.40.3：通过。
- systemd 与 Docker service：通过；`docker info` 返回 Server Version 29.1.3。
- 当前用户 docker 组权限：通过；无需 sudo 访问 daemon。
- PostgreSQL 客户端 16.15：通过。
- `./scripts/check_environment.sh`：全部通过。

尚未运行 Pytest、前端测试或 migration 测试，因为仓库没有对应业务工程。

## 7. 当前已知 Bug

- 尚无已实现业务代码，因此没有已确认的业务 Bug。
- 这不代表系统无缺陷；API、数据库、采集和前端均尚未实现，无法进行运行时缺陷验证。

## 8. 未解决的技术风险

- 当前只验证了 Docker 工具和 daemon，尚未创建项目 Compose 文件或验证 PostgreSQL 容器及应用服务链路。
- AKShare 及其上游接口的稳定性、限流、字段变化和公开/商业使用授权仍需确认。
- 交易日历来源及盘后数据就绪判定尚未选定。
- 股票状态、退市证券和 SH/SZ 代码映射边界尚未形成测试矩阵。
- 不同来源成交量和成交额单位存在映射风险。
- `data_sync_jobs` 的目标范围、成功/失败计数和断点字段尚未定稿。
- 生产负载、数据规模、备份窗口和服务器规格尚无运行数据支持。

## 9. 数据库 Migration 状态

- Alembic 尚未初始化。
- 当前不存在 migration 文件，也未创建数据库表。
- 数据库结构仅为 `PROJECT_PLAN.md` 和 `docs/architecture.md` 中的设计初稿。
- M1-04 必须先确认模型约束和同步任务字段，再创建并测试首个 migration；不得直接修改数据库。

## 10. GitHub 同步状态

- 已配置私有远程仓库 `origin`：`git@github.com:crazychen0530/StockInsight.git`。
- 本地 `main` 已首次推送并设置跟踪 `origin/main`；推送前已确认远程没有既有分支，未覆盖远程历史。
- 未执行强制推送、版本发布或远程分支删除。
- 后续每个验收通过的功能形成逻辑提交；只有获得当次授权后才执行 push。

## 11. 下一个 Codex 会话的具体任务

可直接复制以下指令：

```text
继续开发 /home/crazychen/myprojects/StockInsight，只执行 Milestone 1 的 M1-02：后端基础工程与健康检查。

开始前依次阅读 AGENTS.md、PROJECT_PLAN.md、TASKS.md、SESSION_HANDOFF.md、docs/DECISIONS.md、docs/DEPLOYMENT.md，并检查 git status、最近提交和远程配置。

先运行 ./scripts/check_environment.sh 并确认全部通过。初始化 backend 的 Python 工程配置，仅建立 FastAPI、SQLAlchemy 2、Pydantic、Alembic、Pytest 与 Ruff 基础结构，实现 GET /api/v1/health 和统一配置/测试入口；遵循 API Router -> Application Service -> Repository 分层，不创建股票业务接口或数据库业务表。运行 Ruff、Pytest 和实际健康接口测试，更新 TASKS.md、CHANGELOG.md 与 SESSION_HANDOFF.md，形成逻辑完整的本地提交；未经授权不要 push。
```

## 12. 是否达到购买云服务器条件

未达到。M1-M5 尚未完成，没有可运行 MVP、容器部署验证、采集稳定性证据、访问控制、数据授权确认或备份恢复演练。当前继续本地开发，不购买服务器、不部署公网。
