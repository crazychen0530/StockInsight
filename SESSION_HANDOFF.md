# StockInsight 会话交接

> 更新时间：2026-10-12（Asia/Shanghai）
> 以当前 Git、代码和测试为准；固定模拟行情不代表真实上游验收。

## 1. 当前版本与里程碑

- 目标版本 v0.1.0；M0、M1、M2、M3 全部完成。
- 本会话按用户授权，从 M3-02 连续推进至 M3-04，没有进入 M4。
- 下一任务 M4-01：MA5、MA20、MA60 纯计算模块。
- 已有本地采集 CLI/任务/恢复、股票查询 API、概览/搜索/详情、日 K 线/成交量；尚无均线、数据状态页或自动调度，不等于完整 MVP。

## 2. Git 与 GitHub

- 开始为干净 `feature/m3-01-stock-query-api`，提交 `531ceb2`。
- M3-02：`2342334 feat: unify frontend API client and page framework`。
- M3-03：`aaba460 feat: add dashboard and stock query views`。
- 当前 `feature/m3-04-market-charts`，从 M3-03 创建，M3-04 形成独立 `feat: add daily candlestick and volume charts` 提交；准确 SHA 以 `git log -1 --oneline` 为准。
- 本轮没有合并 main、push、删除分支、创建标签/Release。本轮 `git ls-remote --heads origin main` 已只读核验 GitHub main 为 `68589318270c713fe0a7d59318407c5ee94197ec`，与本地 main/origin/main 一致；M3 四项尚未进入 main。
- origin 为用户既有私有地址 `git@github.com:crazychen0530/StockInsight.git`。M3-01 至 M3-04 代码待授权合并/同步，依 AGENTS.md 未获授权不 push。
- 下轮基于已完成 M3 的功能分支 HEAD，不能从旧 main 直接开始 M4。

## 3. 本轮完成范围与架构检查

- M3-02：同源 Axios `/api/v1`、15 秒超时、类型化股票/日线契约、结构/单位/日期/整数检查、统一固定中文错误及安全 request_id、Loading/Empty/Error 组件、AbortController/序号隔离、三个业务路由和 404。
- M3-03：概览本地股票计数、URL q/page 搜索与分页/返回、详情基础信息和闭区间查询；未知来源/时间不推断，上海时区，1000 条上限和 has_more 提示。
- M3-04：模块化 ECharts SVG K 线和成交量，升序日期、open/close/low/high、联动缩放、成交量零基线、ResizeObserver/卸载 dispose；原始 Decimal 字符串 tooltip/明细，图形坐标近似提示；逐行来源/获取时间与当前显示行汇总。
- 按既有调用方向：页面 -> stocksApi -> Axios -> 只读 Router -> Service -> Repository -> PostgreSQL。未改后端代码、Schema、口径、CLI、采集或调度，没有新增 migration。
- Axios/ECharts 为规划内依赖；Playwright 为可复现浏览器验收开发依赖。没有跨页面共享业务状态或复杂控件需求，暂不引入 Pinia/Element Plus，ADR-018 记录实现细化。
- 详见 [前端专题](docs/FRONTEND_MARKET.md)、[API 专题](docs/STOCK_QUERY_API.md)、[技术决策](docs/DECISIONS.md)。

## 4. 本轮测试与实际结果

- Node 22.23.1；安装时取消 `NODE_TLS_REJECT_UNAUTHORIZED`，保持 TLS；npm 安装/容器 npm ci 审计均 0 vulnerabilities，锁文件已更新。
- M3-02：`npm run typecheck --prefix frontend`、`npm test --prefix frontend`（13 passed）、`npm run build-only --prefix frontend` 通过，形成独立提交。
- M3-03：相同命令通过，21 passed，形成独立提交。
- M3 最终：类型检查、25 项 Vitest（4 文件）、生产构建通过；包含正常/非法响应、原始 Decimal、null 元数据、HTTP/超时/网络错误、取消/晚到/销毁、URL 搜索与分页/返回/详情、Loading/Empty/Error/重试、404/日期/截断、真实 ECharts SVG/双轴缩放/更新/dispose。SSR 测试只替换无 canvas 环境的文字测量，图表构建与 SVG 渲染真实执行。
- 容器：`docker compose exec -T web sh -c 'npm run typecheck && npm test && npm run build-only'` 同样通过（25 passed）。本轮只重建/更新 web 使新锁文件和依赖生效。
- 浏览器：`npm run test:browser --prefix frontend` 通过。先真实 Vite -> API 只读列表，再模拟 HTTP fixture 验证搜索 -> 详情 -> SVG/鼠标缩放/日期/截断/空/503/request_id/重试/390px，无浏览器异常。复现脚本保留 `frontend/scripts/browser-smoke.mjs`。
- 另用 `.venv/bin/python /tmp/stockinsight-m3-real-browser.py` 通过真实 Chromium -> Vite -> Axios -> FastAPI -> Service -> Repository -> PostgreSQL -> SVG，20 条明确模拟日线与来源/精确值可见。新库 `m3_browser_287bd0aa_query_api_test`，仅向该隔离库写 fixture；测试 API 8001/Vite 5174 已由 runner finally 停止，库保留。runner/截图在 /tmp，不是全新 Linux 部署或真实上游验收。
- 浏览器首次因缺少 libnspr4/libnss3 无法启动，官方 Ubuntu 包仅解压 /tmp 后成功；使用现有 Windows 中文字体副本到 /tmp 供截图，不安装系统包、不分发字体。复现本机额外环境：`PLAYWRIGHT_BROWSERS_PATH=/tmp/stockinsight-browser/browsers`、`LD_LIBRARY_PATH=/tmp/stockinsight-browser/libs/usr/lib/x86_64-linux-gnu`、`FONTCONFIG_FILE=/tmp/stockinsight-browser/fonts.conf`。
- 首轮浏览器拖拽断言失败，测试先滚动图表入视口并为滑块留出底部空间后通过；随后发现窄屏 Grid 最小宽度溢出，修复后移动布局断言通过。截图 `/tmp/stockinsight-m3-desktop.png`、`/tmp/stockinsight-m3-mobile.png` 已人工查看。
- `.venv/bin/ruff check backend`、`.venv/bin/ruff format --check backend` 通过（58 文件）。`.venv/bin/python -m pytest backend -q -m 'not postgres'` 在正常权限下 **322 passed、34 deselected**。首次沙箱内运行停在既有子进程相关用例，96 秒后中断，为 278 passed/34 deselected；不计作通过，正常权限复跑 2.47 秒全部通过。
- 本轮未重跑完整 PostgreSQL/migration 升降级；M3-01 历史完整验收为 356 passed 无 skip，首轮既有采集锁冲突复跑通过，风险保留下节。本轮隔离浏览器库仅执行 upgrade head；开发库只读复核。
- `python3 /tmp/stockinsight-m3-doccheck.py`、`git diff --check`：通过：49 个本地链接、44 个围栏块、4 个 Mermaid 块结构，132 个文件私有凭据/Token/私钥模式检查及差异空白检查。

## 5. 当前运行与数据库状态

- 页面：`http://127.0.0.1:5173/`；搜索：`http://127.0.0.1:5173/stocks`。
- API 文档：`http://127.0.0.1:8000/docs`，包含健康、股票列表/搜索、详情、日线四项 GET。
- db/API/web healthy，仅 loopback 5432/8000/5173。原持久卷 `stockinsight-local_postgres_data` 保留。
- 开发库 `stockinsight` 仍 `0001_initial_schema`，stocks/daily_prices/technical_indicators/data_sync_jobs 均 0 行。打开页面应显示空状态；没有自动插入模拟行情或调用真实 Provider。
- 唯一 migration 仍 `0001_initial_schema`。测试模拟数据只存在新隔离库；不向开发库写 fixture，不清库、不删卷。
- 重启后：`docker compose up --detach --no-build --wait --wait-timeout 120`。新增依赖需要重建 web，见 [部署说明](docs/DEPLOYMENT.md)。

## 6. 已知问题和未验证边界

- 详情 ECharts chunk 约 572 KB（gzip 196 KB），Vite 500 KB 警告保留，按详情路由延迟加载；后续 M5 性能复核，不隐藏阈值。
- 大于 JS 安全整数的成交量响应会明确失败，避免静默精度损失；图形价格坐标使用浮点近似，精确字符串在 tooltip/明细。
- stocks 尚无逐行 source/fetched_at，界面为未记录；行情 has_more/空响应不证明覆盖完整或最新。获取时间只表示最后插入/业务值变化时获取时间。
- M3-01 首轮既有采集测试出现 collection_busy，换全新库通过；物理断连释放会话锁窗口仍是待调查假设，本轮没有修改采集互斥。
- 真实 AKShare/上游稳定性、授权、交易日历和盘后就绪尚未验收；没有真实行情展示承诺。
- Docker daemon Registry 直拉网络与沙箱 socket 限制仍在，现有镜像可重建。浏览器宿主运行库/字体是测试环境准备，生产部署另行验收。
- M4 指标/任务状态/调度、M5 全新 Linux、安全/备份恢复/完整 MVP、M6 生产路由回退/反向代理/访问控制未实现。

## 7. 文档与下一任务

已同步 TASKS.md、CHANGELOG.md、README.md、本文件、docs/FRONTEND_MARKET.md、docs/DECISIONS.md（ADR-018）、docs/DEPLOYMENT.md；产品方向和总体架构基线不变。

下次可直接执行：

```text
继续开发 /home/crazychen/myprojects/StockInsight，执行 M4-01：MA5、MA20、MA60 纯计算模块。先依次阅读 AGENTS.md、PROJECT_PLAN.md、TASKS.md、SESSION_HANDOFF.md、docs/DECISIONS.md 及指标相关代码和文档；检查工作区、分支、提交与远程。基于已验收 M3 HEAD 创建 feature/m4-01-moving-averages，保护旧 main 和现有分支。实现独立于 Web/ORM 的确定性计算，按真实交易日升序，窗口不足返回 null，不使用未来数据，精确输入/输出与版本明确；覆盖正常、窗口边界、缺失历史、乱序、重复/非法输入和无未来数据。完成对应测试/Ruff、文档、任务与交接、本地逻辑提交。保持数据库/卷/服务，未经授权不合并/push；M4-02 持久化/API 留待对应任务。
```

## 8. 服务器与同步

不需要购买服务器。M4/M5 尚未完成，仍本地开发，无公网部署。本轮全部功能形成独立本地提交；里程碑结束需要项目所有者决定合并与 GitHub 同步，未经授权不推送。
