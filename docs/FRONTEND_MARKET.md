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
