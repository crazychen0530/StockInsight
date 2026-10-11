# M2-05 本地采集 CLI、任务与恢复

状态：已实现，验收使用明确标记的模拟 Provider/SDK 和全新 PostgreSQL 隔离库；未调用实时行情。入口为 `python -m app.jobs.cli`，沿用配置、JSON 脱敏日志和公开错误，不启动 Web、调度器或隐式 migration。无新依赖、模型或 revision。

## 运行

从仓库根目录使用已安装后端及 `market-data` extra 的 `.venv`。先按 [README](../README.md) 配置环境、启动数据库并显式迁移。CLI 不自动读取 `.env`；已有本地生成的可信配置可按以下方式导入，勿打印密码或使用带密码 URL：

```bash
set -a
source .env
set +a
export APP_ENV=development
export PGHOST=127.0.0.1
export PGPORT="${POSTGRES_PORT:-5432}"
export PGUSER="$POSTGRES_USER"
export PGPASSWORD="$POSTGRES_PASSWORD"
export PGDATABASE="$POSTGRES_DB"
export DATABASE_URL="postgresql+psycopg:///$POSTGRES_DB"
export PYTHONPATH="$PWD/backend"
.venv/bin/python -m app.jobs.cli --help
```

以下命令会访问真实上游并写入当前配置数据库，开发前先确认来源授权和目标库；本轮验收没有执行这些联网命令。先同步股票基础信息，再采集显式股票闭区间：

```bash
.venv/bin/python -m app.jobs.cli stocks
.venv/bin/python -m app.jobs.cli --max-attempts 3 --retry-delay 1 daily \
  --symbol 000001.SZ --symbol 600519.SH \
  --start 2026-09-28 --end 2026-09-29 --job-type backfill
.venv/bin/python -m app.jobs.cli jobs --limit 20
.venv/bin/python -m app.jobs.cli resume <job-id>
```

`<job-id>` 替换为 jobs 输出的 UUID。重试选项在子命令前；`full/incremental/backfill` 是记录的任务类型，都执行给定闭区间，不自动猜测日期或扩大范围。最多 500 个不同股票代码，重复规范化代码、非法代码/日期、反向日期、非法 UUID、limit 越界在初始化 Engine 前拒绝；不提供任意来源、模拟数据、SQL 或 HTTP 触发参数。

stdout 为每任务一个 `job_result` JSON 和末尾 `collection_summary`；日志写 stderr。jobs 仅输出最近记录（1–100 条），不创建任务。每条结果带 `coverage_verified=false`。退出码：0 执行成功/已成功任务恢复为空操作，1 失败/部分失败/操作冲突，2 参数或配置无效，130 可处理的中断。未知异常保存固定错误码并退出 1，不输出原始异常/SQL/连接串。基础设施错误会终止当前调用，不保证未开始的股票已登记；已提交任务可用 jobs 查询。

## 工作项、状态与空响应

复用现有 `DataSyncJob`，不新增持久父任务或股票列表字段：

| 命令 | 持久工作项 | total/success/failure | checkpoint |
| --- | --- | --- | --- |
| daily 一个股票闭区间 | 一个 job，一个股票工作项 | total=1，成功 1/0，失败 0/1 | 非空且业务提交成功后，规范化股票与最后实际返回的交易日期 |
| daily 多个股票 | 每股独立 job；CLI 汇总 succeeded/partial/failed | 每股独立计数；CLI 的 job_count 是任务数 | 每股独立推进；前股成功不被后股失败回滚 |
| stocks 全量快照 | 一个 job，整批原子写入 | 获取/验证前总数未知为 0；成功后 total=返回股票数；失败前无法获知可靠数量时三个计数为 0、status=failed | 整批提交后最后一个实际股票；日期为空 |

计数表示股票工作项，不是日线行数、SQL 影响行数或累计尝试次数。多股 CLI 汇总不是数据库父任务；重新启动多股命令会为各股创建新任务。若需持久化父子批次和逐次历史，另行设计 migration。本阶段不把基础快照拆成逐股事务。

状态为 `pending -> running -> succeeded/failed`。登记 pending、启动 running、终结任务各用短事务；Provider/校验/退避不持有业务事务。多股部分失败保存在各股 failed/succeeded 记录，CLI 输出 partial；本入口不创建单行 partial 状态。

空日线响应表示该股票请求执行成功，success=1，但不代表有行情或范围完整；checkpoint 为空，安全摘要 `empty_response_coverage_unverified`。空股票快照 total=0，同样保留该摘要。空响应不删除旧数据。没有选定交易日历和盘后就绪来源，不使用 `end_date` 冒充实际进度，不承诺补齐所有交易日。

## 重试与恢复

仅 `ProviderError.retryable=true` 自动退避重试；默认最多 3 次（含首次），可设 1–5 次；base_delay 允许 0–10 秒，指数退避上限 30 秒。永久契约错误、Validator 错误、数据库错误不自动重试。重试日志只包含 job_id、错误码、尝试序号、延迟；任务只保存安全错误码，不存原始异常、响应或凭据。来源与任务 source 必须一致，写入前检查。

`resume UUID` 重新读取持久化 source、类型、股票和日期；pending/running/failed 在获得独占锁后按原范围重放，复用同一 ID，重置本次尝试的 started_at、结束时间和计数。已 succeeded 不调用 Provider、不改计数。一次恢复中的自动退避不重置 started_at。尝试历史仅有安全日志，不声称持久审计。

业务提交与任务终结是两个事务：业务提交后崩溃，任务可能仍是 running。checkpoint 仅在业务提交后记录，但不能证明整个请求区间完整，所以恢复始终重放原闭区间，绝不从 checkpoint_date+1 开始。幂等 UPSERT 保持已提交行且补入本次实际返回的缺失行；这是至少一次执行，不是网络调用恰好一次。重放遇到上游修订值时仍沿用既有覆盖规则。

Ctrl-C/SIGTERM 返回 130，保留 running 供明确恢复；真实 CLI SIGTERM 已验证 SDK 子进程回收。SIGKILL 无法处理或保证递归清理所有上游子进程，任务仍为 running；已验证直接采集进程被杀后数据库释放连接与锁，另一进程可恢复。先 jobs 查看 ID，再 resume；不按时间猜测任务过期或自动窃取。

## 并发边界

每个采集任务在专用 AUTOCOMMIT 连接上获取数据库级 PostgreSQL 会话 advisory lock（key `7348190501`），覆盖同库内不同类型和重叠区间的协作 CLI；忙时返回 `collection_busy`。连接在 finally 中 invalidate 物理关闭，避免持锁连接回到池。现有同范围 active 唯一索引仍阻止重复 pending/running，返回 `active_job_exists`，提示先恢复原 ID。多股命令逐任务获取锁，不承诺整个命令不可交错。

这是受控本地入口的互斥协议，不约束绕过入口直接调用 Service 的代码；未实现分布式租约、fencing 或网络分区后的旧执行者防护，不声称具备多主调度能力。机制依据 [PostgreSQL 会话锁说明](https://www.postgresql.org/docs/16/explicit-locking.html#ADVISORY-LOCKS) 和 [SQLAlchemy AUTOCOMMIT 说明](https://docs.sqlalchemy.org/en/20/core/connections.html#understanding-the-dbapi-level-autocommit-isolation-level)。

## 验证与复现

新增 `test_collection.py` 26 个非数据库测试、`test_collection_postgres.py` 10 个 PostgreSQL 测试。覆盖成功/空响应、重试耗尽与失败恢复、全失败/部分失败、重复执行/活动防重、来源不符、全局锁、真实 SIGKILL/SIGTERM、提交后崩溃、实际离线 CLI 与输出脱敏。所有证券与报价均是测试模拟值。

```bash
.venv/bin/python -m pytest backend -q -m 'not postgres'
.venv/bin/ruff check backend
.venv/bin/ruff format --check backend
.venv/bin/python -m pip check
```

完整测试需四个**全新空库**；沿用已导出的 PGHOST/PGPORT/PGUSER/PGPASSWORD，不要删除或复用已有数据库：

```bash
RUN_ID="$(date +%Y%m%d%H%M%S)_$RANDOM"
createdb "m2_05_${RUN_ID}_stocks_test"
createdb "m2_05_${RUN_ID}_migration_test"
createdb "m2_05_${RUN_ID}_prices_test"
createdb "m2_05_${RUN_ID}_jobs_test"
export APP_ENV=test
export STOCK_TEST_DATABASE_URL="postgresql+psycopg:///m2_05_${RUN_ID}_stocks_test"
export TEST_DATABASE_URL="postgresql+psycopg:///m2_05_${RUN_ID}_migration_test"
export DAILY_PRICE_TEST_DATABASE_URL="postgresql+psycopg:///m2_05_${RUN_ID}_prices_test"
export JOB_TEST_DATABASE_URL="postgresql+psycopg:///m2_05_${RUN_ID}_jobs_test"
.venv/bin/python -m pytest backend -q
```

fixture 断言指定后缀及空库；仅清理该轮新建库内自己的测试数据。迁移升降级回归另在 migration_test，开发库 `stockinsight` 和原 Compose 卷保持。当前 323 项完整回归通过，无 skip；运行时测试创建的库名及当前环境证据见 [交接文档](../SESSION_HANDOFF.md)。
