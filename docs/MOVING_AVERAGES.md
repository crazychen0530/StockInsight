# 均线计算与指标更新

M4-01：`app.analysis.moving_averages.calculate_moving_averages` 接收不可变 ClosePoint（股票、真实交易日期、Decimal 收盘价），返回按股票/日期排序的 MA5/20/60。窗口包含当日及此前 N-1 条真实记录；不足返回 null，不使用未来记录，不填充休市日期。拒绝重复日期、非法股票、负数、非有限数和不能精确存入 numeric(18,4) 的输入。

版本 `sma-close-v1` 固定 Decimal 精度 40、ROUND_HALF_UP 四位小数，不依赖调用方 Decimal 精度。只分析已校验且本地实际保存的行情，不能凭记录序列证明交易日覆盖完整。

验证：`.venv/bin/python -m pytest backend/tests/test_moving_averages.py -q`：11 passed，固定模拟数据覆盖窗口边界、分组、乱序、不修改输入、非法值、重复、Decimal 上限/上下文和所有前缀无未来数据。

M4-02：非空行情同步在同一单股事务内写入行情并重算该股票全历史指标；先锁股票行，防止同股票并发重算覆盖。历史补采/修正影响的后继窗口同步更新，值相同保留 computed_at。纯计算不验证整段日历完整；入口复用 OHLCV Validator。现有库历史可通过 M4 本地指标重算命令补齐。

`GET /api/v1/stocks/{symbol}/indicators?start_date=2026-01-01&end_date=2026-04-30&limit=250&calculation_version=sma-close-v1` 只读本地库，升序、闭区间、最大 1000、has_more；Decimal 字符串，历史不足 null，computed_at 为 UTC。未知版本 422，股票不存在 404，存在无指标 200 空列表。source/fetched_at 指当日日线输入，并非整个窗口；不在请求中计算。

`GET /api/v1/system/data-status?limit=20` 最大 100，返回最新持久任务、股票工作项计数、原范围/实际游标/开始结束时间及安全错误码。未知原始错误显示 stored_error_redacted；coverage_verified 固定 false。没有匿名采集 HTTP 入口。

验证（M4-02）：新建六个隔离 PostgreSQL 库完整后端 `370 passed`，含 migration 升降级、历史修正、幂等时间、指标写失败回滚行情、真实 API Decimal/null/版本/上限/空/不存在和状态错误脱敏。旧隔离库 fixture 清理同步加入指标子表；开发库保持原状。
