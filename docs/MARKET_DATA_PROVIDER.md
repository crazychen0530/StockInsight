# M2-01：市场数据 Provider 契约

状态：已实现 Provider 与离线契约测试；真实上游可用性、数据授权与持久化未验收。

## 1. 接口与范围

`backend/app/collectors/provider.py` 定义可替换的 `MarketDataProvider` Protocol：

- `fetch_stocks() -> MarketDataBatch[StockInfo]`：沪深 A 股身份快照。
- `fetch_daily_prices(symbol, start_date, end_date) -> MarketDataBatch[DailyBar]`：规范代码与闭区间日期的不复权日线。

只返回 immutable dataclass 与 tuple；上游 DataFrame、中文字段和调用参数留在适配层。API 未接入 Provider；保持 `Data Worker -> MarketDataProvider -> Validator -> Repository -> Database`。M2-02 已实现[独立 Validator](MARKET_DATA_VALIDATOR.md)，M2-03 至 M2-05 才实现持久化、幂等采集和运维 CLI。

## 2. 字段、口径与缺失信息

| 内部字段 | AKShare 字段/约定 | 转换与边界 |
| --- | --- | --- |
| `StockInfo.symbol/exchange` | `code` | 保留六位字符串与前导零；列表来源为 A 股，6 开头映射 SH，0/3 开头映射 SZ |
| `StockInfo.name` | `name` | 非空字符串，去除首尾空白 |
| `StockInfo.list_date/status` | 接口不提供 | 保留 `None` / `unknown`，不根据名称猜测停牌/退市，不把本次缺席等同退市 |
| `DailyBar.symbol` | 请求代码与返回 `股票代码` | 必须一致；未知市场拒绝，不自动补零猜代码 |
| `DailyBar.trade_date` | `日期` | Python date，必须在请求闭区间内 |
| `open/high/low/close` | `开盘/最高/最低/收盘` | Decimal，人民币元 |
| `volume_shares` | `成交量`（手） | 精确乘 100 后转整数股；拒绝非有限值与非整数股，不能截断 |
| `amount_cny` | `成交额`（元） | Decimal，人民币元，无额外倍率 |
| batch `source/source_interface` | 提供者与具体接口 | `akshare` 与接口名；基础信息上游为沪深京交易所，日线上游为东方财富 |
| batch `fetched_at` | 调用完成时间 | aware UTC；不是交易时间，也不是上游发布时刻 |
| batch `adjustment` | 日线请求 `adjust=""` | 固定 `none`，无复权选项 |
| batch units | 内部统一约定 | `price_unit=CNY`、`volume_unit=share`、`amount_unit=CNY` |

批次元数据适用于其中每条记录，空批次也保留来源与获取时间。后续 Validator/Repository 必须将批次来源、时间和复权口径附加到每条持久化日线；本次没有写库。

基础列表选用 `stock_info_a_code_name`，其返回包含北交所。4/8/92 开头仅在该 A 股列表上下文中判为范围外并排除，日志记录排除数量；其他未知前缀报契约错误。该规则不是任意证券代码的通用 Validator，不支持 B 股、基金、指数或北京行情。不能用这个快照覆盖完整历史证券集合或推断交易状态。

## 3. 上游接口依据

2026-10-11 查阅 [AKShare 官方股票文档](https://akshare.akfamily.xyz/data/stock/stock.html#id28) 与官方实现，并在本地安装 AKShare 1.19.1 后检查签名（未联网采集）：

- [股票基础信息实现](https://github.com/akfamily/akshare/blob/main/akshare/stock/stock_info.py)：`stock_info_a_code_name()` 返回 `code/name`，聚合沪深京列表，无 timeout 参数。
- [历史行情实现](https://github.com/akfamily/akshare/blob/main/akshare/stock_feature/stock_hist_em.py)：`stock_zh_a_hist(symbol, period, start_date, end_date, adjust, timeout)`；固定 `period="daily"`、`adjust=""`，日期按 `YYYYMMDD` 传递。官方文档标记成交量为手、成交额为元。

固定依赖 `akshare==1.19.1` 放在 `market-data` 可选 extra；API 基础安装不强制加载 SDK/Pandas。AKShare 及其 Pandas/NumPy 等传递依赖属于已批准数据栈；传递依赖尚未完全锁定，M5 继续评估。接口升级应重跑固定契约测试和签名检查。

## 4. 失败、空结果与时间边界

- 正常无数据返回空 tuple 与元数据，不补造行情；不表示该日期已完成采集或停牌。
- 支持 SDK 的无列空 DataFrame；若存在列却缺少必需字段，即使没有行也报契约漂移。新增无关列允许，必需列缺失/重复、无法表示的数值或日期报 `provider_contract_error`。
- M2-02 独立 Validator 已负责 OHLC、负值、重复交易日、代码段、精度/数据库范围校验与显式交易日历接口；市场统计异常阈值和日历来源仍未选定。Provider 返回不能被解释为已通过业务校验，调用者须显式串联 Validator。
- `MARKET_DATA_TIMEOUT_SECONDS` 默认 30，须满足 `0 < value <= 300`，由 M1-06 Settings 环境白名单加载。它限制整个 SDK 子进程调用，包含导入和多次内部请求；日线同时传递 SDK 网络 timeout。子进程启动有固定开销，M2-05 批次性能评估时再测量。
- Python 标准库 subprocess 超时后终止并回收子进程。私有 `_akshare_worker` 只隔离一次 SDK 调用，不是采集 CLI、任务 Worker 或调度器，也不运行数据库操作。
- `provider_timeout` 可重试；一般上游失败为 `provider_unavailable`，SDK 未安装为 `provider_dependency_missing`。契约错误/缺依赖不可盲目重试。本次单次调用不自动重试；有限次数/退避、任务状态与恢复留给 M2-05。
- 错误继承现有 `ApplicationError`，可映射安全 503；Provider 仅使用 `stockinsight` 安全日志，记录来源、固定接口名与错误码。SDK Python stdout/stderr、日志和原始异常消息在子进程隔离并丢弃，父进程不记录原始 payload 或异常。没有新增业务 HTTP 路由。

## 5. 离线验证与后续入口

在仓库根目录执行：

```bash
.venv/bin/python -m pip install --editable 'backend[dev,market-data]'
.venv/bin/python -m pip check
.venv/bin/ruff check backend
.venv/bin/ruff format --check backend
.venv/bin/python -m pytest backend -m 'not postgres' -q
```

默认测试不访问任何实时行情接口。`backend/tests/fixtures/akshare/` 是明确标记的模拟数据；可替换 mock Provider 与 AKShare adapter 均接受契约测试。fake SDK 子进程覆盖正常输出、日志/异常抑制、超时实际回收、字段漂移和缺依赖。安装 market-data extra 后另测真实 DataFrame 日期序列化；未安装时该一项明确 skip，核心契约测试仍运行。

现有 Compose API 镜像仅安装 `.[dev]`，未重建或安装可选 SDK；继续提供基础 HTTP 服务。未来 Worker 镜像需显式安装 market-data extra 并注入 timeout；当前不提供采集启动入口。未改变 Compose 服务、数据库表或卷，不需要 migration。

真实上游样本、限流、完整性、稳定性及公开/商业使用许可尚未验证或确认。离线契约测试通过不等于真实行情采集、数据库存储或端到端业务验收。当前继续本地开发，无服务器采购需求。

## M5 真实上游修正

显式环境配置 `MARKET_DATA_DAILY_INTERFACE` 可选 `stock_zh_a_hist`（默认东方财富）或 `stock_zh_a_hist_tx`（腾讯）；Compose automation 默认腾讯。不会失败后静默切换。腾讯行持久来源为 `akshare_tx`，任务 scope 的 `akshare` 表示采集器家族，实际日线来源由 Provider 声明并经 SourceProvider 校验；Repository 不判断第三方接口。字段按[AKShare 官方说明](https://github.com/akfamily/akshare/blob/main/docs/data/stock/stock.md)和安装的 1.19.1 源码核验：腾讯 volume 已为股、amount 已为元，不重复乘 100/10,000。该版本错误地将深市 `000xxx` 股票划入指数分支，适配层为该段补足一次手转股；主板/创业板其他段及科创板沿用 SDK 的股单位。

SDK DataFrame 改用 Python 最短往返数字表示，消除 Pandas `double_precision=15` 制造的浮点尾数，不降低 Validator 存储精度标准。腾讯 SDK 金额乘 10,000 的二进制尾数仅允许在 2 个 IEEE-754 ULP 内还原为分，且 ULP 必须小于半分；有意义的分以下金额仍拒绝。CDR `689xxx.SH` 与北京股票在股票目录适配入口排除，核心代码 Validator 不放宽。

2026-10-12 东方财富日线多次连接失败，腾讯接口实际采集通过；完整证据见 [M5 验收](M5_ACCEPTANCE.md)。上游开源 SDK 的 MIT 许可不等于其聚合数据可公开转载或商业使用。


## 东方财富连接复核（2026-10-12）

本轮直连与环境代理均返回 HTTP 200；项目原有 AKShare 1.19.1 Provider → Validator 对贵州茅台、平安银行各取回 2026-01-05～10-09 的 183 条真实不复权日线，腾讯同区间同样通过。此前失败当前无法复现，不能认定根因是登录、封 IP 或接口失效，也不声称做了已证实的根因修复。没有修改 SDK、降低 TLS 校验、增加 Cookie 或自动换源。诊断命令、排错与替代方案见 [数据源诊断](MARKET_DATA_DIAGNOSTICS.md)。


## 网页策略与可追溯备用（2026-10-12）

用户授权新增`PolicyProvider`，在启用`SOURCE_POLICY_DIRECTORY`时优先于原`MARKET_DATA_DAILY_INTERFACE`，每次股票请求读取共享有限JSON配置。三种mode：prefer_eastmoney、eastmoney、tencent。前者在东方财富Provider错误（不含SDK缺依赖/来源不匹配）、校验错误、空响应或调度目标日缺失时尝试腾讯；程序缺陷、配置损坏和存储错误不触发换源。每次尝试保留既有超时，重试仍由CollectionRunner有界执行。固定来源失败不换源。

成功批次保留实际akshare/akshare_tx和接口/UTC时间；SourceProvider及ReadyProvider读取最终动态来源，存储与指标事务不变。安全日志记录原来源、备用来源、原因码和最终来源；失败任务保留最终错误，未新增持久尝试表。调度日历校验和目标收盘日就绪检查对两个来源都执行；手动历史采集无就绪日要求，但空响应在策略模式下视为无法获取。

GET/PUT /api/v1/system/source-policy经Service与专用文件Repository处理，PUT仅允许development、本机Host/Origin、管理口令认证；不在HTTP请求执行采集。JSON严格枚举和revision，文件锁、临时文件/fsync/原子替换防半写，旧revision返回409。新进程读取同文件保证持久化，损坏显式503。production写入403，API禁用目录时503。口令不返给客户端、不进入日志/构建/localStorage；访问与修改有安全应用日志。初始配置/权限与使用见[README](../README.md#网页采集来源设置与使用教程)。

实际验收：网页三模式切换、错误口令拒绝、刷新持久化、口令清空、教程链接、桌面/390px手机通过，最终prefer_eastmoney。调度容器两只真实样本东方财富失败后自动腾讯返回各183条且来源akshare_tx；只读验证未覆盖原行情。配置变化不使已成功任务失效，已有行情仍可能来自腾讯。
