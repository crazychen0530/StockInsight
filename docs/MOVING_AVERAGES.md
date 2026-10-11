# 均线计算与指标更新

M4-01：`app.analysis.moving_averages.calculate_moving_averages` 接收不可变 ClosePoint（股票、真实交易日期、Decimal 收盘价），返回按股票/日期排序的 MA5/20/60。窗口包含当日及此前 N-1 条真实记录；不足返回 null，不使用未来记录，不填充休市日期。拒绝重复日期、非法股票、负数、非有限数和不能精确存入 numeric(18,4) 的输入。

版本 `sma-close-v1` 固定 Decimal 精度 40、ROUND_HALF_UP 四位小数，不依赖调用方 Decimal 精度。只分析已校验且本地实际保存的行情，不能凭记录序列证明交易日覆盖完整。

验证：`.venv/bin/python -m pytest backend/tests/test_moving_averages.py -q`：11 passed，固定模拟数据覆盖窗口边界、分组、乱序、不修改输入、非法值、重复、Decimal 上限/上下文和所有前缀无未来数据。
