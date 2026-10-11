# M4 本地增量、补采与恢复手册

所有命令在仓库根目录运行；操作者须拥有本机 shell、数据库写入/任务权限和获准的行情源访问权。页面/API 只读，不提供公开管理接口。固定测试样例只能用于新隔离库，禁止把模拟行情写进开发或真实业务库。

## 1. 环境与前置检查

```bash
cd /home/crazychen/myprojects/StockInsight
git status --short --branch
docker compose ps
PYTHONPATH=backend .venv/bin/python -m app.jobs.cli --help
PYTHONPATH=backend .venv/bin/python -m app.jobs.scheduler --help
```

首次新开发机按 README 安装后端 `.[dev,market-data]`；只有访问真实 AKShare 的采集/调度入口需要 market-data extra，查询和本地指标重算无需 SDK。Python 不自动读取 .env。已有 Compose .env 不覆盖，原数据卷不删除；migration 必须显式执行 `docker compose exec -T api alembic upgrade head`，M4 没有新增 revision。

宿主 CLI 使用已有本地数据库；若默认端口/用户/库名不同，按私有 .env 调整下列非敏感值。密码交互读取，不写入 shell 历史或仓库；不要把连接串/密码复制到报告。

```bash
export APP_ENV=development
export PGHOST=127.0.0.1 PGPORT=5432 PGUSER=stockinsight PGDATABASE=stockinsight
export DATABASE_URL=postgresql+psycopg:///stockinsight
read -r -s -p '本地 PostgreSQL 密码: ' PGPASSWORD
export PGPASSWORD
```

先核对所选数据库和当前任务；持久任务保存固定安全错误码，不记录原始上游错误。本文后续采集命令会访问真实上游并写入所选库，验收演练使用隔离库+离线 SDK，未对开发库执行这些采集命令。

## 2. 基础信息、历史补采和手工增量

```bash
PYTHONPATH=backend .venv/bin/python -m app.jobs.cli stocks
PYTHONPATH=backend .venv/bin/python -m app.jobs.cli daily \
  --symbol 000001.SZ --start 2026-01-01 --end 2026-09-29 --job-type backfill
PYTHONPATH=backend .venv/bin/python -m app.jobs.cli daily \
  --symbol 000001.SZ --symbol 600519.SH \
  --start 2026-09-28 --end 2026-09-29 --job-type incremental
```

先同步 stocks，再采非空日线。手工 incremental 仍是操作者指定闭区间，需依据当前本地水位选择并重叠最近一天；自动水位由调度器计算。backfill 用于更早缺口或修正；相同股票/日期 UPSERT 不重复，业务值相同不改写 fetched_at，MA 值相同不改写 computed_at。非空单股行情与全历史均线在同一事务提交；失败不留下半股数据。多股票逐股独立任务，部分失败保留已完成股票。

预期 stdout 包含 job_result 与 collection_summary：succeeded 退出 0，partial/failed 退出 1，参数/配置错误退出 2，中断退出 130。total/success/failure 为股票工作项数，不是行情行数；`coverage_verified=false` 始终提醒尚未证明完整日历覆盖。手工 CLI 的空响应是操作成功且附 empty_response_coverage_unverified，不代表已更新；调度器另有当日就绪检查。

## 3. 已有历史指标补齐

```bash
PYTHONPATH=backend .venv/bin/python -m app.jobs.cli indicators --symbol 000001.SZ
```

只读取本地行情并重算 `sma-close-v1`，不初始化/调用 Provider。使用采集锁和股票行锁，整股事务；stdout indicator_result 含 changed_count。第一次补齐返回实际插入/变化数，重复不变返回 0；无本地股票为 stock_not_found，存在但无行情返回 changed_count=0。此操作不创建采集任务，不把重算时间冒充数据获取时间。

检查 API 和页面：

```bash
curl --noproxy '*' 'http://127.0.0.1:8000/api/v1/stocks/000001.SZ/indicators?start_date=2026-01-01&end_date=2026-09-29&limit=1000'
curl --noproxy '*' 'http://127.0.0.1:8000/api/v1/system/data-status?limit=20'
```

详情页 `http://127.0.0.1:5173/stocks/000001.SZ` 展示 MA5/20/60、版本/来源/计算时间；不足窗口为 —，未计算没有记录时提示本地重算。状态页 `http://127.0.0.1:5173/data-status` 显示安全错误/原范围/游标。空库预期为空，不自动填充。

## 4. 失败、中断与原任务恢复

```bash
PYTHONPATH=backend .venv/bin/python -m app.jobs.cli jobs --limit 20
# 将下面的占位值替换成 jobs 返回的实际 UUID；保持原范围恢复。
PYTHONPATH=backend .venv/bin/python -m app.jobs.cli resume '<job-uuid>'
```

先确认原进程已正常结束并检查数据源/参数/权限。collection_busy 表示其他协作采集仍持锁，应等待或由操作者处理原进程；active_job_exists 表示已有同范围 pending/running，应根据 ID 恢复，不改表状态、不猜测超时、不广泛 kill。恢复失败/中断任务复用原 ID 和完整原范围，幂等重放，业务提交后游标推进；成功任务 resume 为空操作。指标失败会回滚该股行情；修复后 resume 即可，不手工改指标表。不要执行 down -v、truncate、reset 或破坏性 downgrade。

daily_data_not_ready：核实是否停牌、交易日历是否正确、上游是否已包含当日数据；调度器最多按 retry policy 重试，耗尽记失败，不能以旧行情替代。日历覆盖错误：由操作者补全并核验日历后重启，不能用 weekdays 临时填充。详细独立调度命令、锁/退出码和 --once 行为见[调度手册](SCHEDULER.md)。

## 5. 可复现的离线演练

本机 Compose PostgreSQL 可达且私有 .env 已建立时：

```bash
.venv/bin/python scripts/test_postgres.py
.venv/bin/ruff check backend scripts/test_postgres.py
.venv/bin/ruff format --check backend scripts/test_postgres.py
npm run typecheck --prefix frontend
npm test --prefix frontend
npm run build-only --prefix frontend
```

`test_postgres.py` 只连接 loopback 的 postgres 管理库并创建随机唯一的六个隔离空库；通过后保留库用于排查，不重置任何已有库，不输出凭据。完整测试包含 migration 升降级，因此绝不能用业务数据库替代测试 URL。新环境需按 README 准备 Node 22 和依赖；浏览器脚本 `npm run test:browser --prefix frontend` 需要本地 web/API、Playwright Chromium 与运行库。

M4 演练结果：真实 CLI 子进程离线 SDK 执行 backfill、两股 partial、失败/成功 resume、jobs 和 incremental，行情/指标保持 2 行；本地 indicators 第一次补齐 65 行、再次 changed_count=0；独立 scheduler --once 两次验证首次 partial、重启成功跳过/失败 ID 保留、原始错误不泄漏。全部在新隔离库运行。另有真实浏览器 -> Vite -> API -> PostgreSQL 验收 20 条明确模拟日线、MA5/20 与不足 MA60、任务状态；开发库原四表和卷保留。真实上游/交易日历及全新 Linux 验收留 M5。
