# StockInsight 会话交接

> 更新时间：2026-10-12（Asia/Shanghai）
> 以当前 Git、代码和测试为准；模拟行情不代表真实上游验收。

## 1. 当前里程碑与授权

- 目标版本 v0.1.0，M0–M4 全部完成。
- 本会话用户明确授权从 M4-01 连续完成整个 M4 后停止；已完成五项，没有进入 M5。
- 当前支持股票搜索/详情、K 线/成交量/MA5/20/60、数据状态、本地采集/恢复/重算和独立盘后调度。
- 下一任务 M5-01：完整核心测试与 v0.1.0 验收准备；不等于已完成 M5/M6。

## 2. 本轮实现和架构

- M4-01：不可变 ClosePoint/MovingAverage，按股票/日期排序，Decimal 固定 Context 精度 40、HALF_UP 四位，版本 sma-close-v1；窗口不足 null，无未来记录、无日历日填充；输入严格校验。
- M4-02：非空 DailyPriceService 单股票事务内写行情和全历史指标；股票行锁串行化并发写/重算，版本 UPSERT，值相同保留 computed_at，补采历史/修正重算后继窗口。沿用原表，没有 migration/新依赖。
- 两个新 GET：`/api/v1/stocks/{symbol}/indicators` 和 `/api/v1/system/data-status`。只读数据库、日期闭区间/上限/has_more、版本/null/精确 Decimal 字符串和安全错误；指标来源只代表当日输入，任务计数为股票工作项。
- M4-03：详情 ECharts LineChart MA5/20/60，日期关联、null 不连线、精确 tooltip/明细、版本/来源/计算时间；指标加载/错误独立，不阻断日线。图表在明细前。`/data-status` 提供最新任务状态/计数/范围/错误/游标、刷新/空错重试。
- M4-04：独立 `app.jobs.scheduler`，Shanghai 可配置盘后时间、受控 JSON 日历来源/覆盖、调度锁/采集锁、成功当日游标跳过、失败/中断原 ID 重放、重叠最近本地日期增量、当日数据未就绪失败和有界重试、逐股成果保留/批次 partial。正常锁退出主动 unlock 再关闭，缩短原断连释放窗口。
- M4-05：`cli indicators --symbol` 本地补齐，无 Provider 初始化；完整增量/补采/恢复手册与可复现六隔离库测试脚本。
- 保持 Router -> Service -> Repository -> Database 与独立纯 Calculator；API 生命周期不导入/启动 scheduler，没有公开采集入口、Schema/核心栈/单位/部署变化。

## 3. 测试与实际结果

- `.venv/bin/python scripts/test_postgres.py`：**383 passed，13.83 秒，无 skip**，新建六个随机唯一空库，保留库供排查。包含 migration 升降级/再升级、既有采集/查询回归和 M4 集成。
- 新增纯计算 11 项：窗口/分组/乱序/无未来前缀/非法输入/大 Decimal/调用方精度与 Inexact trap 隔离。显式模拟数据。
- 指标 PostgreSQL：同事务失败回滚行情、历史修正/插入、并发不相交追加后的全历史正确性、幂等时间、真实 API null/Decimal/版本/日期/上限/404/空和任务原始错误脱敏。
- 调度：8 项离线固定时钟/日历测试，真实数据库双锁/重启跳过/失败原 ID/未就绪重试/partial/水位。真实独立 scheduler CLI 子进程使用离线 SDK 和测试注入时钟两次 --once，首次 partial，第二次成功股票跳过且失败任务 ID 复用；生产入口没有假时钟参数。
- 真实采集 CLI 子进程演练 backfill、partial、failed/succeeded resume、jobs、incremental，重复后行情/指标各 2 行；本地 indicators 首次补齐 65 行，重复 changed_count=0，不创建 Provider。
- `.venv/bin/ruff check backend scripts/test_postgres.py`、`.venv/bin/ruff format --check backend scripts/test_postgres.py`：通过，73 文件格式；`.venv/bin/python -m pip check`：无依赖冲突。
- Node 22.23.1：`npm run typecheck --prefix frontend`、`npm test --prefix frontend`：**31 passed**；`npm run build-only --prefix frontend`：通过。均线响应/状态错误校验、组件状态和真实 ECharts SVG 对齐/null/tooltip 已覆盖。
- `npm run test:browser --prefix frontend`：通过真实 Vite -> API 只读列表，再使用浏览器 HTTP 模拟 fixture 验证均线图例、搜索/详情/SVG/鼠标缩放/日期/截断/空/错/重试、390px、状态空页，无浏览器异常；调整图表至明细前后复跑通过。
- `.venv/bin/python /tmp/stockinsight-m4-real-browser.py`：新库 m4_browser_052c1775_query_api_test，模拟 Provider -> 持久 CollectionRunner 任务 -> 行情/均线 -> 真实 Chromium/Vite/Axios/FastAPI/Repository/PostgreSQL/SVG/status 全链路通过。20 条明确模拟日线、MA5/20 与不足 MA60、成功任务可见。专用 8001/5174 服务 finally 停止，原服务保留；脚本/截图在 /tmp，不当作全新 Linux 或真实上游验收。
- 本机浏览器运行环境沿用 M3：PLAYWRIGHT_BROWSERS_PATH=/tmp/stockinsight-browser/browsers、LD_LIBRARY_PATH=/tmp/stockinsight-browser/libs/usr/lib/x86_64-linux-gnu、FONTCONFIG_FILE=/tmp/stockinsight-browser/fonts.conf；未系统安装或分发字体。
- 文档链接、围栏/Mermaid 结构、真实私有凭据/Token/私钥扫描与 git diff --check 通过，最终数量以交付工具输出为准；未以结构检查冒充 Mermaid 渲染。
- 首轮完整测试失败原因是新增指标子表未纳入旧 fixture 清理、模拟日期包含周末、旧 OpenAPI 路由断言未更新；均修复后在新空库完整复跑通过。没有沿用失败结果计作通过。

## 4. 本地运行和数据保护

- db/api/web 均 healthy，只绑定 loopback 5432/8000/5173，原卷 stockinsight-local_postgres_data 保留。
- 开发库 stockinsight：0001_initial_schema，stocks/daily_prices/technical_indicators/data_sync_jobs 均 **0 行**（本轮只读复核）。页面应显示空状态，未填充模拟行情/触发真实采集。
- 真实 HTTP API 与 Vite 代理 data-status 均 200 空列表；OpenAPI 六个 GET 路由验证通过。依赖未变化，原容器源码挂载热更新，本轮无需重建服务。
- 默认 Compose 仍三服务，没有自动常驻 scheduler。操作者提供完整已核验日历/目标股票/起始日后，按 docs/SCHEDULER.md 启动；这避免未经配置的真实网络采集。
- scripts/test_postgres.py 每次创建六个新隔离库并保留，不清任何现有库。测试使用 .env 本机连接信息，不输出凭据，迁移升降级只作用于随机空测试库。

## 5. Git 与 GitHub

- 2026-10-12 用户明确授权 M4 完成后本地合并并推送；先 fetch origin main，确认远程仍为 12a3005、工作区干净且为 M4 祖先。
- 已将 feature/m4-01-moving-averages 快进合并本地 main，无冲突，合并后与验收功能分支代码树完全一致。
- M4-01 0a99d42、M4-02 6071b81、M4-03 5c8a9c0、M4-04 7ca0085、M4-05 30730a3 五项全部完成并正常推送 origin/main。
- git ls-remote 核验远程代码交付 SHA 为 30730a31b231ab7ec224d9896c170e9916c9bd76，与本地一致；本同步记录另行提交并同步，最终 HEAD 见 Git 和交付报告。
- 当前分支 main，工作区在提交后应干净，功能分支保留；origin 为既有私有仓库。未强推、删除分支、创建标签/Release 或部署公网。
- 合并后复核：后端离线 341 passed、42 deselected（PostgreSQL），前端类型/31 项测试、Ruff/格式通过。未重跑完整 PostgreSQL/migration/浏览器/构建，代码树未变，原完整 383 项及浏览器证据保留。
- 推送前扫描五项提交覆盖的 188 个 blob，真实本机私有凭据、Token/私钥模式、真实 .env 和超大文件检查通过。

## 6. 已知限制和后续验收

- 真实 AKShare 稳定性/上游授权、经核验完整交易日历和盘后就绪运维仍待 M5；测试日历/fixture 不证明真实市场可用。
- 调度当天收盘数据缺失（包括可能停牌）记录 failed；需人工核验。每 daemon/天一批、每股有界重试，耗尽后本日需明确重新运行 --once/重启。覆盖外拒绝执行，不用 weekdays 猜测；更新日历需重启。
- 自动增量水位不证明历史完整，早期缺口/修正需显式 backfill；全历史指标重算优先正确性，长期大数据量需后续实测优化。
- 双会话锁约束协作入口，不声称分布式 fencing 或任意直接 Service 调用互斥；崩溃锁释放仍依赖 PostgreSQL 回收。原 M3 已知物理断连窗口已改为正常退出显式 unlock，真实进程崩溃场景由既有 SIGTERM/SIGKILL 测试覆盖。
- stocks 无逐行来源/时间列，仍 null；指标 source 指当日输入，不是整个窗口全部来源。has_more/空和获取时间不证明覆盖完整/最新。
- 大成交量超过 JS 安全整数会明确拒绝；图形坐标浮点近似、明细字符串精确。
- 详情 chunk 约 602 KB（gzip 207 KB）保留 Vite 500 KB 警告，M5 性能复核，不隐藏阈值。
- Docker daemon Registry 直拉网络与沙箱 socket 限制仍在；生产 SPA 回退/反向代理/访问控制、全新 Linux、备份恢复属于 M5/M6。

## 7. 文档与下一会话

已更新 TASKS、CHANGELOG、README、交接、ADR-019、architecture、DEPLOYMENT、FRONTEND_MARKET、COLLECTION_CLI，并新增 MOVING_AVERAGES、SCHEDULER、OPERATIONS。产品方向/总体架构基线不变。

```text
继续开发 /home/crazychen/myprojects/StockInsight，执行 M5-01：核心后端/前端/migration/端到端验收。先依次阅读 AGENTS.md、PROJECT_PLAN.md、TASKS.md、SESSION_HANDOFF.md、docs/DECISIONS.md 和 M4 三份专题，检查工作区、分支、提交和远程。当前 M4 五项已快进合并 main 并同步 GitHub；从已同步的干净 main 创建 M5 功能分支，保护已有分支和开发库，不自动推送或清库。用 scripts/test_postgres.py 创建新隔离库复现完整回归，整理十类测试证据和真实上游/交易日历/性能/部署边界，完成任务文档及本地提交。M5-02 全新 Linux 与后续任务只按新的授权推进，M6 不启动。
```

## 8. 服务器与同步

无需购买服务器，尚未满足 M5 MVP、安全、真实上游/授权、全新 Linux 和备份恢复条件。M4 五项已按用户授权合并并同步 GitHub，本同步记录随后的文档提交一并同步；没有公网部署。真实股票/日线/指标/任务库仍为空，常驻调度未启动。M4 完成指 TASKS.md 规定的代码、隔离测试和文档标准，不能表述为页面已有真实行情或自动更新已实际运行。
