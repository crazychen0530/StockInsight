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
