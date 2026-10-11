# M3 前端查询与行情展示

## API 与页面框架（M3-02）

页面 -> `stocksApi` -> 同源 Axios `/api/v1` -> Vite `/api` 代理 -> 既有只读 API。15 秒超时，无自动重试，无服务端密钥。错误统一为固定中文提示及经过格式检查的服务端 request_id，不呈现原始异常、HTML、连接配置或 details。空/格式异常的成功响应作为 invalid_response，不冒充空列表。

`/` 概览，`/stocks` 搜索，`/stocks/:symbol` 详情，其余路径 404。页面共享 Loading/Empty/Error 状态组件。`useRequest` 在新查询和组件销毁时取消请求，并以递增序号隔离晚到响应。取消依据 [Axios AbortController 官方文档](https://axios-http.com/docs/cancellation)。

股票 null 来源/获取时间保持缺失，不推断。Decimal 保留字符串；成交量要求 JS 安全整数，超过安全范围的响应明确报格式错误，避免展示已经损失精度的数值。未新增依赖 Pinia/Element Plus：当前没有跨页面共享业务状态或需要 UI 组件库的控件；按既有规划在实际需要时引入。

## 验证

使用 Node 22，保持 TLS 校验：

```bash
env -u NODE_TLS_REJECT_UNAUTHORIZED npm ci --prefix frontend
npm run typecheck --prefix frontend
npm test --prefix frontend
npm run build --prefix frontend
```

默认测试只使用明确标记的模拟 API fixture，不向开发库注入行情。后续真实上游验收、M4 均线/数据状态与 M5 全新环境验收分别推进。

## 基础视图（M3-03）

概览展示本地 stocks 总数与搜索入口，不推导行情覆盖率或最近采集时间。搜索提交关键词、分页写入 URL（q/page），浏览器返回可恢复查询；详情链接使用规范代码。页面加载、新搜索、翻页和仅切换 symbol 时重新查询，并隔离旧响应。

详情显示基础元数据和显式日期区间，缺失项为“未记录”/“未知”。默认近一年，今天按上海时区计算。每次最多 1000 条最早日线，has_more 明确提示缩小范围，不声称完整；日期不合法或倒置时阻止请求。保留精确行情字符串，逐行来源/时间按 Asia/Shanghai 展示。不加入后台采集按钮。

M3-03 验证：类型检查、21 项组件/API 测试和生产构建通过。模拟固定 fixture 覆盖概览、搜索提交/分页/返回/详情、Loading/Empty/Error/重试、404、空行情、日期与截断提示。测试通过真实 Vue Router 驱动视图，但不等同于真实上游或浏览器端到端验收。

## K 线与成交量（M3-04）

ECharts 模块化导入、SVG 渲染、双 grid，共享日期轴并联动 inside/slider dataZoom。K 线顺序为 open/close/low/high；成交量为股，红涨绿跌。日期副本升序，API 层拒绝重复日、越界/错股、无效日期/时间和不安全成交量；不自行计算指标。组件在尺寸变化时 resize，卸载 dispose。

图形坐标为浮点近似，tooltip/表格使用原始 Decimal 字符串和精确金额。表格逐行展示 OHLCV、成交额、来源和上海时间，图表上方展示已显示记录的来源集合与最大获取时间；这不证明最新采集或交易日完整性。图表加载失败仍可查看明细。

实现参考 [ECharts 模块导入与 SVG Renderer 官方说明](https://echarts.apache.org/handbook/en/basics/import/)。详情按路由延迟加载；当前生产详情 chunk 约 572 KB、gzip 196 KB，有 500 KB 体积警告，保留为 M5 性能复核项。无 Pinia/Element Plus、数据库、API 或采集变更。

## 浏览器复现

保留 `scripts/browser-smoke.mjs`，Playwright 为开发依赖；测试要求已运行本地 web/API，不自行启动、迁移或清理数据库：

```bash
cd frontend
npx playwright install chromium
npm run test:browser
```

可用 `STOCKINSIGHT_WEB_URL` 指定另一本机 Vite 入口。测试先验证真实 Vite -> API 的只读列表响应，再通过明确模拟的 HTTP fixture 验证搜索 -> 详情 -> SVG/鼠标缩放/日期/截断/空/错误/重试/390px 布局。截图默认写 `/tmp/stockinsight-m3-desktop.png`、`/tmp/stockinsight-m3-mobile.png`，不进入 Git；模拟数据不写数据库。真实市场数据和完整 Linux 端到端验收仍待后续任务。

本轮验收结果（2026-10-12）：25 项前端测试、宿主/容器类型检查与构建、Chromium 桌面/390px 交互通过；新隔离 PostgreSQL 的 20 条模拟日线经真实 API/Vite 到浏览器 SVG 通过。后端非 PostgreSQL 回归 322 passed、34 deselected，Ruff/格式通过；没有重跑完整数据库升降级。原开发库四表仍空、原卷与三服务健康。详细首次失败、修复、运行库与命令记录见[交接](../SESSION_HANDOFF.md)。

## M4-03 均线与数据状态

详情页与日线并行读取本地指标 API（独立取消/错误状态）。ECharts 注册 LineChart，MA5/20/60 按日期关联，缺失值为 null、不连空值、不在浏览器重算。图例可切换，tooltip/指标明细保留 Decimal 原字符串；来源为当日输入，明确版本、计算时间、不复权/人民币元和历史不足。指标失败时保留日线展示。DataStatus `/data-status` 只读最近 20 项任务，展示股票工作项计数、范围、上海时间、游标和安全错误码；空/错误/重试/刷新可见，不提供匿名采集入口。

验证：前端类型、31 项测试、生产构建通过；真实 ECharts SVG 覆盖均线对齐和 null 断线。Chromium 验证均线图例、搜索/详情、滑块、日期/截断/空/错/重试、390px 和状态空页面通过，fixture 仅 HTTP 拦截。详情 chunk 约 602 KB（gzip 207 KB），原 Vite 大包提示仍存在，留 M5 性能复核。

## M5 真实运行补充

2026-10-12 已在用户授权下填充真实目录与四只股票行情：首页明确默认覆盖，搜索/详情/K 线/MA/任务状态通过原开发环境及全新 Linux 的独立真实浏览器验收。此前章节的模拟数据/空开发库是对应历史会话的证据，当前结果以 [M5 验收](M5_ACCEPTANCE.md)为准；不把 5,223 只目录股票误称为均已采集日线。
