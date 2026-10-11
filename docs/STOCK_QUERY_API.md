# M3-01 股票查询 API

本地数据库只读入口，不调用 Provider、不触发采集或指标计算。固定模拟行情只用于隔离测试库，开发库不会自动填充数据。OpenAPI：`http://127.0.0.1:8000/docs`。

## 接口与参数

所有路径前缀为 `/api/v1`，仅支持 GET。

| 路径 | 参数 | 返回 |
| --- | --- | --- |
| `/stocks` | `query` 默认空、最多 128 字符；`page` 默认 1、至少 1；`page_size` 默认 20、1–100 | `items,total,page,page_size` |
| `/stocks/{symbol}` | 复用 Validator 的 SH/SZ 支持代码段与规范化规则 | 股票对象 |
| `/stocks/{symbol}/prices` | 必填 `start_date,end_date`；`limit` 默认 250、1–1000 | 显式范围、`items,limit,has_more` 与单位/口径 |

列表 query 去除首尾空白，代码/名称大小写不敏感的字面包含搜索；`%`、`_` 作为普通字符。按 symbol 升序，越界页返回空 items，total 为全部匹配数；拒绝 NUL 与超出 PostgreSQL BigInt 的分页偏移。

代码按现有 Validator 规范化，不通过外部证券查询补充存在性。日期使用 `YYYY-MM-DD`，校验复用日期范围规则（起始不得晚于结束）。日线查询为闭区间，按 trade_date 升序，最多返回 limit 条；额外读取一行判断 has_more。has_more 为 true 时可将下一次 start_date 设为最后返回日期的下一天，保持 end_date 不变。跨请求结果可能受采集更新影响，不提供跨请求快照游标。

## 响应与数据口径

股票字段为 `symbol,name,exchange,list_date,status,source,fetched_at`。未知 status/list_date 保持已有值；现有 stocks 无逐行来源/获取时间，**source 和 fetched_at 固定为 null**，不从日线或最新任务推断。本次不改 Schema。

日线字段为 `symbol,trade_date,open,high,low,close,volume_shares,amount_cny,source,fetched_at,adjustment`。OHLC 和成交额采用 Decimal 的 JSON 字符串，避免浮点精度损失；成交量为整数。响应顶层明确 `price_unit=CNY,volume_unit=share,amount_unit=CNY,adjustment=none`。逐行保留来源，fetched_at 序列化为 UTC 时区时间。该时间是该行最后一次插入或业务值变化时的获取时间；同值重采不会更新它，因此不代表最近尝试采集时间。

已存在股票没有区间行情：200、空 items、has_more=false；本地没有该股票：404。空结果/has_more=false 只反映数据库行数，不证明交易日覆盖完整、最新或上游就绪。返回数据不代表投资建议。

## 错误与运行边界

复用统一 顶层 `code,message,request_id,details`，不回显 SQL、连接串或原始异常。

| HTTP | 语义 |
| --- | --- |
| 422 | 非法代码、日期、搜索/分页/limit，或缺少必填参数 |
| 404 | `stock_not_found`，本地股票不存在 |
| 503 | 数据库配置/连接/查询不可用；列表沿用 `stock_storage_error`，详情/日线为 `stock_query_unavailable` |
| 500 | 未预期内部异常，统一安全错误 |

Router -> StockQueryService -> StockRepository/DailyPriceRepository -> PostgreSQL；列表复用 StockService.search。同步路由在线程池调用同步 SQLAlchemy，ORM 对象在 Session 内转为响应模型。每应用按需创建 Engine/Session 工厂，应用关闭时 dispose；健康检查不依赖数据库连接或配置，不自动 migration。API 事务设置 PostgreSQL read-only；列表 total/items 和日线存在性/数据各自使用 REPEATABLE READ 同快照。此事务限制不等于生产账号权限配置完成。

保持原 Compose 三服务、开发库和卷，无新依赖、migration、前端、调度或公网部署。

## 本地只读示例

```bash
curl --fail --silent 'http://127.0.0.1:8000/api/v1/stocks?query=000001&page=1&page_size=20'
curl --silent 'http://127.0.0.1:8000/api/v1/stocks/000001.SZ'
curl --silent 'http://127.0.0.1:8000/api/v1/stocks/000001.SZ/prices?start_date=2026-09-01&end_date=2026-09-30&limit=250'
```

空开发库中列表应为空，详情/日线应为 404；这些命令不创建数据。需要数据时按[本地 CLI 文档](COLLECTION_CLI.md)另行操作，真实上游尚未验收。

## 验证与复现

```bash
.venv/bin/python -m pytest backend -q -m 'not postgres'
.venv/bin/ruff check backend
.venv/bin/ruff format --check backend
```

新增 28 个非 PostgreSQL 测试和 5 个 PostgreSQL API 集成测试，覆盖参数/错误/精度/单位/来源、只读事务、并发快照和 Provider 禁止调用。完整回归需分别新建空库并注入 `STOCK_TEST_DATABASE_URL`（`*_stocks_test`）、`DAILY_PRICE_TEST_DATABASE_URL`（`*_prices_test`）、`JOB_TEST_DATABASE_URL`（`*_jobs_test`）、`TEST_DATABASE_URL`（`*_migration_test`）、`QUERY_API_TEST_DATABASE_URL`（`*_query_api_test`），通过 PG* 私下传入凭据后运行 `.venv/bin/python -m pytest backend -q`。不得复用非空库或指向开发库；fixture 首先检查空库，再 Alembic upgrade/check。查询 fixture 的写入/清理由独立测试连接承担，HTTP 使用真实只读应用连接。

官方行为参考：[FastAPI 同步路由](https://fastapi.tiangolo.com/async/)、[Pydantic Decimal 序列化](https://docs.pydantic.dev/latest/api/standard_library_types/#decimals)。本轮实际结果与测试库见[交接文档](../SESSION_HANDOFF.md)。
