# M2-04：日线采集、区间补采与部分失败处理

状态：已实现 Service/Repository；固定模拟 Provider 与真实 PostgreSQL 隔离库验收通过。真实上游采集稳定性尚未验收；未新增 CLI、任务记录、自动重试、断点、HTTP API、调度、前端或 Schema。

## 1. 调用链与入口

```text
未来受控本地入口 -> DailyPriceService.sync / sync_many
                 -> MarketDataProvider.fetch_daily_prices(symbol, start_date, end_date)
                 -> validate_daily_prices(batch, symbol, start_date, end_date, trading_dates=...)
                 -> StockRepository.exists(symbol)
                 -> DailyPriceRepository.upsert(batch) -> PostgreSQL daily_prices
```

Service 接收既有 session factory，Provider 显式注入；基础信息先通过 StockService 同步。参数、整个股票列表及可选交易日历在首次采集前检查；代码规范化后不允许重复。共享日期必须为 date 且 start_date <= end_date。显式日历由纯函数 `validate_trading_dates` 校验并冻结，避免采集中途变化；不增加框架依赖。

每只股票先采集并校验完整批次，再打开 Session 和事务；网络调用期间不持有数据库事务。非空批次检查 stocks 外键对象，缺失时返回 `daily_stock_missing`，不自动创建猜测的基础信息。Repository 不采集、不校验业务输入、不 commit。

## 2. 闭区间与数据口径

调用方显式传入闭区间 `[start_date, end_date]`，原样交给 Provider。Validator 要求返回记录属于该股票和区间，重复日期、区间外日期或任意非法 OHLCV 都使整只股票失败；不通过静默裁剪掩盖来源异常。乱序记录排序后写入。补采可以反复请求相同、重叠或旧区间；保留本次未返回日期和区间外已有数据，不删除停牌/缺失记录。

复用 M2-01/M2-02 的不复权 `none`、Decimal 人民币元、股和人民币元成交额口径，不再手转股或舍入。每条日线写入 source、UTC fetched_at、adjustment；单位由既有 `*_shares`、`*_cny` 字段与数据库约束表达。source_interface 保留于同步收据，现有表没有接口审计列。没有新增模型或 migration，head 仍为 `0001_initial_schema`。

未提供 trading_dates 时只有既有周末、日期范围和获取时间等检查；传入集合时逐条核对成员资格。两种方式都不证明所有应有交易日已返回，也不判断停牌、节假日全集或盘后数据就绪。空结果返回 processed_count=changed_count=0，不连接数据库、不检查股票是否已存在、不清空旧数据；应由未来任务/数据质量流程区分无交易、无数据和未就绪。

## 3. UPSERT 与事务

| 场景 | 行为 |
| --- | --- |
| 新 `(symbol, trade_date)` | 插入 OHLCV、成交额和来源/时间/口径 |
| 已有行数值、来源或口径不同 | 原子更新这些字段和 fetched_at |
| 所有数值、来源和口径相同 | 不执行 UPDATE，即使新 fetched_at 更晚也保留原行 |
| 一只股票超过 500 行 | 分块 SQL，所有块处于该股票同一个事务 |
| 校验、连接、写入或提交失败 | 不返回成功收据；该股票尚未提交的全部变化回滚 |
| 其他股票已提交 | 保留；已知单股票错误不阻断后续股票 |

使用 `ON CONFLICT(symbol, trade_date) DO UPDATE ... WHERE ... IS DISTINCT FROM ... RETURNING trade_date`；返回行数是实际新增/修改数，避免 rowcount=-1。无需先查询每个主键，不重复插入，并发相同输入只产生一份行与一次实际变化。参考 [SQLAlchemy PostgreSQL UPSERT](https://docs.sqlalchemy.org/en/20/dialects/postgresql.html#insert-on-conflict-upsert) 与 [事务上下文](https://docs.sqlalchemy.org/en/20/orm/session_basics.html#framing-out-a-begin-commit-rollback-block)。

fetched_at 表示当前保存值对应的获取时间，不是最后一次尝试时间或区间覆盖水位；每次尝试的批次时间仍在收据返回。不同值冲突按数据库写入顺序生效，当前没有来源版本、陈旧数据拒绝或并发重叠任务锁；不能声称 fetched_at 比较已保护最新行情。未来需要该策略时须明确来源版本语义。指标更新仍属于 M4。

## 4. 收据、部分失败与安全

`sync` 返回不可变 `DailyPriceSyncResult`：symbol、start_date/end_date、processed_count、changed_count、source/source_interface/fetched_at。成功收据和日志在 commit 完成后产生；processed_count 为校验后条数，changed_count 为新增与修改之和，不声称全部为新增。

`sync_many` 按请求股票顺序返回不可变 `DailyPriceBatchResult.results`，每项为成功收据或 `DailyPriceFailure(symbol, code, field, row_index)`。摘要的 success_count/failure_count/empty_count 按股票计数，status 为 empty（空列表）、succeeded（无失败）、partial（成功与失败并存）、failed（全失败）。空响应计入 success_count，同时计入 empty_count；这些只表示调用执行结果，不表示完整区间采集验收，也不是 data_sync_jobs 状态。

ProviderError、MarketDataValidationError、缺失基础信息以及 SQLAlchemy 存储错误逐股票记录并继续；后者转换成固定 `daily_price_storage_error`（503）。日志只记录安全代码、规范 symbol、校验位置和计数，不输出原始异常、SQL 参数或连接串。未知程序错误继续抛出，避免把缺陷伪装成可重试的数据错误；之前已提交股票仍保留。

本阶段没有自动重试或持久断点。调用方排除故障后显式再次执行相同请求，可幂等补齐失败项；M2-05 再接入 CLI、任务状态、退避和恢复。

## 5. 验证与复现

```bash
.venv/bin/ruff check backend
.venv/bin/ruff format --check backend
.venv/bin/python -m pip check
.venv/bin/python -m pytest backend -m 'not postgres' -q

# 先创建三个全新空库，凭据通过现有 PG* 注入；每次运行更换唯一前缀。
APP_ENV=test \
STOCK_TEST_DATABASE_URL=postgresql+psycopg:///new_m2_04_stocks_test \
DAILY_PRICE_TEST_DATABASE_URL=postgresql+psycopg:///new_m2_04_prices_test \
TEST_DATABASE_URL=postgresql+psycopg:///new_m2_04_migration_test \
.venv/bin/python -m pytest backend -q
```

新增 19 个服务单元测试和 12 个真实 PostgreSQL 测试。非数据库回归 268 passed、19 deselected；完整回归 287 passed、无 skip。覆盖收据/单位、空结果、参数预检、区间外/重复/晚到非法行拒绝、超时、缺失基础信息、提交失败、跨股票部分成功、手动恢复、并发幂等、数值极限与 502 行跨 SQL 失败后整股回滚。所有行情均明确为模拟值，没有请求实时行情或向开发库写入 fixture。

日线 fixture 只接受新的空 `*_prices_test`，通过现有 Alembic 升级及 check，无 create_all；每项仅清理该新库的模拟日线与股票，结束保留在 head。股票集成使用独立 `*_stocks_test`；完整升降级另用 `*_migration_test`，结束回到 base。无 URL 时对应 PostgreSQL 测试跳过，不能将这种运行称作全量验收。实际库名和命令见 [会话交接](../SESSION_HANDOFF.md)。
