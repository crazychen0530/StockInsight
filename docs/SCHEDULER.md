# 独立盘后调度

M4-04 入口为 `python -m app.jobs.scheduler`，不在 API 导入、启动事件或 Compose 默认服务中运行。复用现有 Provider、Validator、CollectionRunner、每股独立事务及持久任务；没有新依赖、表或 migration。

## 日历与配置

操作者须提供经核验的 SH/SZ 交易日历 JSON，来源、覆盖起止日期、完整交易日列表均必填。不能把下面的结构样例当成真实日历；样例只列出两个模拟交易日。私有日历建议放仓库外，禁止写入凭据。

```json
{
  "source": "fixture_simulated_example_only",
  "coverage_start": "2026-09-28",
  "coverage_end": "2026-09-29",
  "trading_dates": ["2026-09-28", "2026-09-29"]
}
```

生产使用前需依据交易所公告维护完整列表，记录核验来源和版本；当前没有自动拉取/保证正确的真实日历。重复日期、周末、越界日期、缺失来源拒绝启动。当前上海日期在覆盖外时拒绝执行；休市或未到配置时间返回 `not_due`。initial-start 必须位于覆盖内，并保证从该日期到当前完整覆盖。

## 本地运行

先按[操作手册](OPERATIONS.md)配置数据库环境与可选 SDK、同步股票基础信息。以下日历路径须替换成真实已核验文件，symbol 可重复传入、上限 500。

```bash
cd /home/crazychen/myprojects/StockInsight
PYTHONPATH=backend .venv/bin/python -m app.jobs.scheduler --help
PYTHONPATH=backend .venv/bin/python -m app.jobs.scheduler \
  --calendar /absolute/path/verified-calendar.json \
  --symbol 000001.SZ --symbol 600519.SH \
  --initial-start 2026-01-01 --at 17:30 --once
```

`--at` 为 Asia/Shanghai 的本地时间，默认 17:30，不能早于 15:00，不受宿主机时区影响。去掉 `--once` 后以 30 秒轮询运行，Ctrl-C/SIGTERM 退出 130；每进程每天只尝试一批，每股票内部默认最多 3 次、可配置 1–5 次，指数退避 1、2 秒（基数 0–10 秒）。失败后本日再次尝试需明确重新运行 --once 或重启进程，避免无限调用上游。默认不启动常驻进程；修改日历/配置后重启生效。

## 防重、恢复和结果

- 专用 PostgreSQL 调度锁串行化同库调度 tick，既有采集锁继续串行化 CLI/调度采集。竞争返回 scheduler_busy/collection_busy，退出 1；不强制接管或终止其他进程。
- 成功且 checkpoint 到当日的增量范围，在重启后跳过，不调用 Provider。旧空响应成功没有当日游标时重新采集。失败/中断任务复用 ID/原范围；活动采集仍持锁时不恢复。不同日期残留活动任务应按操作手册人工检查/恢复。
- 新日期范围从本地最近交易日开始重叠一日；首次从 initial-start 开始。只取不晚于当日的本地水位，补齐空档并重算指标。旧历史缺口/修正须显式 backfill，水位不证明完整覆盖。
- 当日日线不在响应中，记录 daily_data_not_ready 并有界重试，重试耗尽为 failed。停牌也可能失败，需要核验，不能用旧行情当作成功。响应中不在日历的日期拒绝；OHLCV/元数据仍由原 Validator 校验。存在当日记录也不证明历史完整。
- 每股任务独立提交；单股失败继续其他股票，stdout scheduler_result 汇总 succeeded/partial/failed，failed_jobs 非零退出 1；配置失败退出 2。单股任务持久化 succeeded/failed，批次 partial 在汇总中，不伪造现有表没有的父批次。
- 锁正常退出时显式 unlock 后关闭专用连接，减少断连释放窗口；崩溃时仍依赖 PostgreSQL 会话回收。不声称分布式 fencing 或绕过入口的直接 Service 调用互斥。

## 验收证据

固定时钟/模拟日历和 Provider 覆盖上海盘前/盘后、节假日、覆盖不足、非法配置、未就绪和部分成功。全新隔离 PostgreSQL 验证独立连接锁、CLI 采集锁、失败重试、持久成功跳过、失败原 ID 重放、重叠水位和单股成果保留。实际独立 scheduler CLI 子进程经离线 SDK/固定测试时钟两次 --once，首次 partial，第二次跳过成功股票且复用失败 ID，错误不泄漏原文；生产 CLI 没有模拟时钟/数据参数。真实上游稳定性和真实交易日历运维仍留 M5 验收。

## M5 实际运行配置（2026-10-12）

仓库 `config/calendars/sse_szse_2026.json` 根据[上交所全年休市公告](https://www.sse.com.cn/disclosure/announcement/general/c/c_20251222_10802507.shtml)及[深交所全年公告](https://investor.szse.cn/disclosure/notice/general/t20251222_618087.html)的节假日区间与周末休市规则生成，覆盖全年 242 个交易日。调休上班的周末仍休市；日历不猜测临时停市或停牌。到期前更新并重启进程。

`--catch-up` 是显式可选模式：盘前、周末或节假日以最近已收盘交易日为目标；当天到达配置的盘后时间后改为当天。daemon 按目标交易日记录本进程已尝试范围，补昨天不会阻止今天 17:30 的更新；成功水位继续由数据库持久化防重。无日历覆盖仍拒绝执行，失败仍有界重试，不修改时钟。

Compose 的 `automation` profile 提供独立 scheduler，默认 4 只股票及腾讯接口，`restart: unless-stopped`；启动/停机/重启均与 API 分离。首次历史范围与股票名单位于 Compose command，修改后重建容器；不是所有 5,223 只目录股票的行情订阅。配置与真实证据见 [M5 验收](M5_ACCEPTANCE.md)。

```bash
docker compose --profile automation up -d --no-build scheduler
docker compose logs --tail 30 scheduler
docker compose restart scheduler
# 明确停止自动更新，保留业务数据及容器
docker compose stop scheduler
```
