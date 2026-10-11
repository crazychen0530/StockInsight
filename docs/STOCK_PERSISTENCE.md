# M2-03：股票基础信息同步与搜索持久化

状态：已实现 Application Service/Repository，固定模拟 Provider 与真实 PostgreSQL 隔离库验收通过。没有新增 HTTP API、CLI、日线采集、任务调度、前端或 Schema。

## 1. 调用链与入口

```text
未来受控采集入口 -> StockService.sync(provider)
                  -> MarketDataProvider.fetch_stocks()
                  -> validate_stocks(batch)
                  -> StockRepository.upsert(records) -> PostgreSQL stocks

未来查询入口 -> StockService.search(query, page, page_size)
             -> StockRepository.search(...) -> PostgreSQL stocks
```

Service 接收现有 `sessionmaker[Session]`，Provider 作为 sync 参数显式注入。网络与整个批次的 Validator 校验在数据库 Session/事务打开前完成；查询不依赖 Provider，也不会因无结果发起采集。Repository 接受已校验的内部 DTO，只负责 SQL 和 DTO 映射，不调用网络、迁移或 commit。

同步通过 SQLAlchemy `session.begin()` 包围整批 UPSERT（每条 SQL 最多 500 行）；正常退出提交，写入或提交失败回滚，不返回成功收据。基础信息快照采用整批原子事务；M2-04 日线跨股票部分失败和 M2-05 重试/断点/任务状态另行实现。实现参考 [SQLAlchemy PostgreSQL UPSERT](https://docs.sqlalchemy.org/en/20/dialects/postgresql.html#insert-on-conflict-upsert) 与 [事务上下文](https://docs.sqlalchemy.org/en/20/orm/session_basics.html#framing-out-a-begin-commit-rollback-block)。

## 2. 新建、更新与幂等规则

| 字段/场景 | 行为 |
| --- | --- |
| 新股票 | 按规范 symbol 插入 name/exchange/list_date/status，允许 None/unknown |
| 已有 name/exchange | 更新为校验后的当前值 |
| 已有 list_date | 输入 None 时保留；输入已知日期时更新 |
| 已有 status | 输入 `unknown` 时保留；输入其他已提供状态时更新，不根据名称推断 |
| 本次缺席股票 | 保留，不删除、不自动改成退市 |
| 相同数据再次同步 | 主键防重；更新条件仅在字段实际不同才执行，重复行不改写 |
| 空批次 | 返回 0/0 收据，不连接数据库，不清空原数据；不表示来源完整或同步任务业务验收 |
| 非法/重复输入 | Validator 抛出固定规则错误，尚未写库 |

使用 `ON CONFLICT(symbol) DO UPDATE`，状态/日期保护在同一 SQL 中完成，不采用先查询再更新的竞态写法。实际变更数使用 `RETURNING symbol` 的返回行数，避免当前 psycopg/SQLAlchemy 的 `rowcount=-1` 行为。

`StockSyncResult` 返回 `processed_count`（校验后处理条数）、`changed_count`（新建与修改条数之和，不单独声称新增数量）以及输入批次的 source/source_interface/fetched_at。收据只在事务提交后返回；空结果单独以 0 条表达。

现有 `stocks` 表只有五个基础字段，没有逐行来源、版本或获取时间列。本次保留批次元数据在同步收据中，不声称已实现持久化逐字段审计或快照版本控制。已知字段并发更新按数据库提交顺序生效，不能用当前 Schema 拒绝陈旧快照；后续若要求持久化来源/版本，须先确认设计并创建 migration。无业务数据/Schema 改动，因此本次不增加 revision。

## 3. 搜索契约

`StockService.search(query="", page=1, page_size=20)` 返回不可变 `StockSearchPage(items, total, page, page_size)`；items 复用 StockInfo，不向调用方泄漏 ORM Session 或模型。

- query 为最多 128 字符的字符串，去首尾空白，禁止 NUL。空字符串列出本地股票。
- 对规范代码（含后缀）和名称执行不区分大小写的字面子串匹配；`%`、`_` 与转义字符按字面处理。使用绑定参数，不拼接用户输入到 SQL。
- page 为正整数，page_size 为 1–100（拒绝 bool）；offset 必须可由 PostgreSQL BigInt 表示。按 symbol 升序稳定分页，超过末页返回空 tuple 与真实 total。
- total 与 items 在同一个 REPEATABLE READ 事务快照中读取；测试覆盖在两条查询之间并发插入，当前页面仍保持一致，下一查询看到新记录。
- 只有代码/名称搜索，没有全文索引、模糊拼音或复杂排序；当前子串查询性能未做生产规模评估，未擅自增加索引。

## 4. 错误与安全

复用 M1-06 ApplicationError/stockinsight 日志。参数错误为 `invalid_stock_search`（422）；SQLAlchemy 存储错误包装为固定 `stock_storage_error`（503），不输出原始 SQL 参数、连接串、查询文本或异常消息。Provider/Validator 错误保留其原类型与固定诊断字段并记录安全日志；未新增 HTTP 绑定或任务状态。

Mock/fixture 数据只用于单元测试与独立测试库。本次未运行真实 AKShare 拉取或向开发库写入模拟证券；业务入口接入前仍需确认真实来源与授权。

## 5. 可复现验证与隔离边界

```bash
.venv/bin/ruff check backend
.venv/bin/ruff format --check backend
.venv/bin/python -m pip check
.venv/bin/python -m pytest backend -m 'not postgres' -q

# 由运维先创建两个全新空库，凭据通过既有 PG* 环境注入，不能复用开发库。
APP_ENV=test \
STOCK_TEST_DATABASE_URL=postgresql+psycopg:///new_m2_03_stocks_test \
TEST_DATABASE_URL=postgresql+psycopg:///new_m2_03_migration_test \
.venv/bin/python -m pytest backend -q
```

新增服务单元测试 16 项、PostgreSQL 集成测试 6 项；后者仅接受独立 `*_stocks_test`，且启动时要求空表，通过现有 Alembic revision 升级（不使用 create_all）。每项只清理本轮新测试库的模拟 stocks，结束保留库在 head。完整 migration 回归仍使用另一个新空 `*_migration_test`，最终回到 base。两个 URL 相互隔离，默认不提供 URL 时 PostgreSQL 测试不会运行。

实际完整回归 256 passed、无 skip；非 PostgreSQL 回归 249 passed、7 deselected。覆盖真实提交后独立连接读取、重复同步不改写、未知信息保护、缺席/空结果、字面匹配/分页、跨 SQL 分块失败回滚与恢复、并发 UPSERT、查询一致快照；未修改前端，不重复前端测试。

初次完整回归发现 `rowcount=-1`，改为 RETURNING 后用另一对全新数据库复测通过。具体库名与验证记录见 SESSION_HANDOFF.md；开发库 stockinsight 和原持久卷保留，三服务继续运行。下一任务为 M2-04 日线幂等采集/补采，不需要购买服务器。
