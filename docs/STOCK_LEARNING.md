# 股票入门学习中心

2026-10-13，项目所有者授权的首版后教育扩展；关联 ADR-029 与 EDU-01。

## 使用路径与学习目标

首页“股票入门 · 从看不懂到会读图”→ `/learn`，也可从导航“股票入门”或使用教程进入。

六课顺序为：股票是什么、看懂行情数字、读懂一根K线、成交量与均线一起看、从图表走向公司、了解交易流程与风险。

页面提供六题即时解释、可纠错/重置的当前页进度、28项术语搜索及读图练习清单。课程全部可直接阅读，不设置测验解锁门槛。重新加载或离开页面后进度重置；不持久化、不收集个人信息。

完成目标是能说明数据与图表含义、分清委托和成交、知道交易前核对规则和风险。无法保证阅读者理解所有知识，也不保证获利。真实交易由用户通过持牌券商独立决定，本平台没有下单或开户功能。

## 实现与边界

- `frontend/src/content/learning.ts`：类型化课程、问题、术语和官方来源。
- `frontend/src/views/LearnView.vue`：课程、内存进度、词典和练习入口。
- `frontend/src/components/LearningCandle.vue`：独立教学SVG，固定虚构数值，不调用市场API、不写入数据库，不计算真实指标。
- 首页入口与学习资源不依赖行情API成功；路由延迟加载。
- 红K线示例同时展示“收盘高于开盘但低于前收盘”，绿K线示例反向对照；图中文字不只依赖颜色。
- 学习内容使用原生锚点、radio、select、label、fieldset和状态反馈，支持键盘操作；手机改为单列。
- API、数据库、Alembic、采集、均线算法和现有部署拓扑不变；不新增依赖。

## 内容来源与维护

核对日期：2026-10-13。

- [上交所股票投资一件事](https://one.sse.com.cn/onething/gptz/)：开户与交易操作的官方核对入口。
- [上交所交易规则（2026年修订）](https://www.sse.com.cn/lawandrules/sselawsrules2025/stocks/exchange/c/c_20260424_10816482.shtml)：交易制度与适用规则入口，实际交易需核对生效安排。
- [上交所证券买卖投教](https://investor.sse.org.cn/knowledge/stock/deal/)与[深交所投教](https://investor.szse.cn/)：继续学习入口。

课程为原创概括，不大量转载原文，不嵌入外部脚本。板块权限、T+1适用品种、申报单位、费用、涨跌幅与除权规则有适用条件；不写“所有股票统一100股/10%”或固定税费。修改涉及具体规则时必须复核官方有效文件并更新核对日期。估值仅介绍基本概念，不声称平台已有财报或估值数据。

## 验收命令

在项目Node22环境中：

```bash
cd frontend
npm run typecheck
npm test
npm run build
```

浏览器验收使用隔离本机Vite端口（不操作原服务）：

```bash
npm run dev -- --host 127.0.0.1 --port 5181 --strictPort
# 另一个终端，使用已准备的Playwright浏览器：
node scripts/browser-learning.mjs
```

浏览器脚本给首页API返回明确的模拟离线错误，验证离线首页入口、课程锚点、K线切换、测验纠错、词典、直接刷新、390px手机无横向溢出及键盘。截图写入 `/tmp/stockinsight-learning-desktop.png` 和 `/tmp/stockinsight-learning-mobile.png`。

2026-10-13实际结果：类型检查、44项前端测试和生产构建通过；上述Chromium交互/布局验收全部通过，无页面脚本异常。另存首页和手机首屏预览 `/tmp/stockinsight-learning-home.png`、`/tmp/stockinsight-learning-mobile-top.png`。原详情chunk约604KB的既有构建警告保留，学习页约22.26KB（gzip10.42KB）。测试浏览器从官方TLS地址断点续传后验证125,797,539字节与ZIP CRC，运行库仅从Ubuntu软件包解压到/tmp；未安装系统包。若使用该临时浏览器，需显式设置 `PLAYWRIGHT_CHROMIUM_EXECUTABLE` 与对应 `LD_LIBRARY_PATH`，常规已安装Playwright环境无需设置。

## 发布说明

截图测试环境最初没有中文字体，曾出现方框；最终仅将Ubuntu文泉驿字体软件包解压到/tmp，以独立Fontconfig配置复验通过。应用沿用系统中文字体栈，无新增在线字体或字体依赖。

开发Vite读取新源码；生产Caddy与匿名预览使用镜像内 `/srv`，仅修改源码或执行 `stockinsight.sh start/public` 不会自动更新已有静态镜像。当前成果需要按现有运维边界发布新的静态资源镜像，并对 `/learn` 的SPA回退进行验收。本轮不自动重建原代理或调整公网窗口。
