# StockInsight 会话交接

> 更新时间：2026-10-10（Asia/Shanghai）
>
> 本文件记录可核验的当前状态。新会话开始时必须结合 Git、任务清单和实际环境重新确认；不得把规划内容当作已实现功能。

## 1. 当前版本与里程碑

- 目标版本：`v0.1.0`
- 当前完成阶段：Milestone 0（项目初始化与长期文档）
- 下一个阶段：Milestone 1（前端、后端、数据库基础工程）
- 当前交付性质：项目管理与架构文档；尚无可运行的股票业务功能

## 2. 当前 Git 状态

- 当前分支：`main`
- 上游分支：`origin/main`
- 最近功能提交：`7bbaa00 docs: add long-term development handoff rules`
- 本次状态同步提交：`docs: record GitHub initial synchronization`
- 远程仓库：`git@github.com:crazychen0530/StockInsight.git`
- GitHub 推送：首次推送已获项目所有者明确授权并成功完成

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

尚未实现 FastAPI、Vue、数据库表、Alembic migration、行情采集、指标计算、定时任务或页面展示。

## 4. 正在开发的功能

当前没有正在开发的股票业务功能。本次会话只完善长期开发管理文件；完成文档验收后结束，不启动 M1 实现。

## 5. 未完成任务

下一阶段优先任务来自 `TASKS.md`：

1. M1-01：准备 Node.js 22 LTS、Docker Engine 和 Docker Compose，并记录可复现的环境检查结果。
2. M1-02：初始化 FastAPI、SQLAlchemy 2、Pydantic、Alembic、Pytest 和 Ruff 工程，实现健康检查。
3. M1-03：初始化 Vue 3、TypeScript 和 Vite 工程。
4. M1-04：确认 `data_sync_jobs` 的范围、计数和断点字段后，创建首个 migration。
5. M1-05/M1-06：建立本地 Compose、配置、日志、统一错误和测试 fixture。

不得跳过 M1 直接实现实时行情、AI 预测、自动交易或其他后续范围。

## 6. 最近一次实际测试及结果

本次文档任务实际执行并通过：

- 必需文档和目录存在性检查。
- Markdown 本地链接目标检查。
- Markdown 代码围栏平衡检查。
- Mermaid 围栏数量与决策记录结构检查。
- `PROJECT_PLAN.md`、`TASKS.md`、`AGENTS.md` 与本交接文档关键规则检查。
- 常见凭据模式扫描。
- `git diff --check`。

M0 初始化时还实际验证过 `.gitignore` 对 `.env`、虚拟环境、`node_modules`、日志和 PostgreSQL 数据目录的匹配规则。

未运行 Pytest、前端测试或 migration 测试，因为仓库当前没有对应工程或业务实现。不得将文档校验描述为业务链路测试。

## 7. 当前已知 Bug

- 尚无已实现业务代码，因此没有已确认的业务 Bug。
- 这不代表系统无缺陷；API、数据库、采集和前端均尚未实现，无法进行运行时缺陷验证。

## 8. 未解决的技术风险

- 当前本机 Node.js 为 18.19.1，未达到目标 Node.js 22 LTS。
- 当前本机未安装 Docker Engine 和 Docker Compose。
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
继续开发 /home/crazychen/myprojects/StockInsight，只执行 Milestone 1 的 M1-01 环境前置检查与方案确认。

开始前依次阅读 AGENTS.md、PROJECT_PLAN.md、TASKS.md、SESSION_HANDOFF.md、docs/DECISIONS.md、docs/DEPLOYMENT.md，并检查 git status、最近提交和远程配置。

请重新检测 Python、Node.js、npm、Docker Engine、Docker Compose 和 PostgreSQL 客户端版本。先报告 Node.js 22 LTS 与 Docker/Compose 的缺口及安全安装方案；未经我确认，不执行需要 sudo、外部下载或系统级修改的安装操作，不开始 M1-02，不实现股票业务功能。完成后更新 TASKS.md 与 SESSION_HANDOFF.md，并报告实际检查命令、结果、Git 状态、GitHub 同步建议及是否需要购买服务器。
```

## 12. 是否达到购买云服务器条件

未达到。M1-M5 尚未完成，没有可运行 MVP、容器部署验证、采集稳定性证据、访问控制、数据授权确认或备份恢复演练。当前继续本地开发，不购买服务器、不部署公网。
