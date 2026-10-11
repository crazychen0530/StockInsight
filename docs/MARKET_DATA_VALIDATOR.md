# M2-02：内部行情 Validator

状态：已实现并通过固定模拟数据离线验收。未连接数据库、实时行情、业务 API、CLI 或调度器。

## 1. 调用边界

`backend/app/collectors/validator.py` 仅使用标准库与 M2-01 DTO，无 Web、SQLAlchemy、SDK、Pandas、环境配置或日志依赖：

```python
from app.collectors.validator import validate_daily_prices, validate_stocks

stocks = validate_stocks(provider.fetch_stocks())
prices = validate_daily_prices(
    provider.fetch_daily_prices(symbol, start_date, end_date),
    symbol,
    start_date,
    end_date,
    trading_dates=confirmed_trading_dates,
)
```

以上是未来 Worker 的组合方式，本次未新增可执行采集入口。保持 `MarketDataProvider -> Validator -> Repository`，后续 Repository 只接收经过校验的内部数据。Provider 负责外部字段映射和手转股；Validator 检查现有单位，绝不再次换算，也不接受浮点数或字符串替代 Decimal。

## 2. 股票与日期

| 项目 | 本版规则 |
| --- | --- |
| 代码规范化 | 仅去首尾空白、后缀转大写；要求 ASCII 六位数字与显式 SH/SZ 后缀；不推断交易所、不补零 |
| SH 支持段 | `600/601/603/605/688` 前缀 |
| SZ 支持段 | `000/002/003` 前缀、`001200–001999`、`300000–309799` |
| 范围外代码 | 北京、B 股、基金、指数、存托凭证、未知/未支持代码段拒绝；不会静默跳过 |
| 股票字段 | symbol 与 exchange 必须一致；名称最多 128 字符、status 最多 24 字符，非空且不得包含 NUL；去首尾空白 |
| 上市信息 | list_date 允许 None；否则必须为 date，且不晚于批次获取时的上海业务日期；unknown 状态保持原义，不根据名称猜测，不自定状态枚举 |
| 请求日期 | 必须是 date，开始不晚于结束；闭区间，允许单日；不接受 datetime/string 自动截断或解析 |
| 行情日期 | 与请求代码一致，日期在闭区间内，且不晚于批次获取时的上海业务日期 |
| 重复与乱序 | 重复股票/交易日直接拒绝（包括代码规范化后重复）；通过校验后按 symbol/交易日升序返回，不覆盖或删除重复行 |

代码段是本版显式支持范围，不代表某代码已发行、仍上市或当前可交易；其他代码段需重新核对再扩展。代码不存在/退市状态应由后续基础信息与业务用例核实，不能从编码推断。M2-01 适配器的 6/0/3 市场映射比本层宽，Provider 返回仍须经过 Validator。

编码参考：[上交所 A 股列表](https://www.sse.com.cn/assortment/stock/list/share/)、[深交所证券代码区间表（2024 年 4 月）](https://www.szse.cn/marketServices/technicalservice/doc/P020240510623040090566.pdf)、[深交所代码区间表（2024 年 12 月）](https://www.szse.cn/marketServices/technicalservice/doc/P020241212550140892927.pdf)。后两项官方检索摘要分别区分 001 的 A 股/存托凭证以及创业板股票/存托凭证边界；本次浏览工具未能打开 PDF 全文，不把这些支持范围表述为当前全部官方代码规则。

## 3. 数值、单位与异常边界

- open/high/low/close 必须为有限、非负 Decimal，满足 `low <= open <= high` 与 `low <= close <= high`。零值和相等价格按既有数据库非负规则允许，不补造停牌行情。
- 价格必须能在 `numeric(18,4)` 中精确表示，金额必须能在 `numeric(24,2)` 中精确表示；超出有效小数位或整数位直接拒绝，不让 PostgreSQL 隐式舍入。额外尾零不改变数值，可以通过。
- 返回 Decimal 只移除数值不变的冗余尾零，并将零规范化为 Decimal(0)，避免巨大冗余 exponent 进入数据库驱动；不舍入或改变原对象。
- 使用 Decimal 的原始 digits/exponent 检查精度，避免 quantize/normalize 受到调用者 Decimal context 的精度、舍入或 trap 影响。极大/极小 exponent 拒绝时不构造巨大中间数。
- volume_shares 必须是 Python int（拒绝 bool、float、Decimal），范围 `0..2**63-1`。金额非负，单位为元；成交量已经是股。
- 这些上限源于已有 ORM/migration 的可表示范围。本版没有未经批准的市场价格上限、成交量启发式阈值或统一涨跌幅阈值；通过校验不证明真实报价、正常市场量级或数据源完整性。

## 4. 元数据、空结果与交易日历

批次来源/接口不能为空、不得有 NUL 或外围空白，长度分别不超过 32/128。只接受 `adjustment=none`、`price_unit=CNY`、`volume_unit=share`、`amount_unit=CNY`；保留来源/接口/单位口径。获取时间必须有时区，转成 UTC 保留同一时刻；上海业务日期仅由该批次获取时刻推导，不读取当前时间，使结果可复现。

空批次是合法的明确无数据结果，仍须通过元数据、请求和日历参数校验；保留元数据与空 tuple。它不代表同步任务完成、停牌或缺失数据已得到解释。

`trading_dates` 接受调用者提供的 date set/frozenset；提供后每行日期须属于该集合，空集合拒绝全部非空行情。无论是否提供日历，周末日期拒绝。`None` 只做周末/日期范围检查，不能识别法定节假日、临时休市或保证区间完整。日历来源尚未决定，本次不联网获取或虚构；后续 Worker 若声明完整交易日验收，必须传入已确认来源、覆盖请求区间的日历，并另行检查数据就绪与缺日。

## 5. 错误与验证

失败抛出 `MarketDataValidationError(ValueError)`，只携带固定 `code/field/row_index`，不保留原始输入或响应。规则失败使该批次不返回校验结果；不部分丢弃非法行。后续任务编排需捕获该错误，使用现有安全日志记录规则/字段/行号并更新任务失败或部分失败状态；本次不引入任务状态写入或 HTTP 错误映射。

返回新不可变批次与记录，不修改输入；重复执行对结果幂等。基础信息 status 仅校验存储边界，后续状态合并不能用 unknown 覆盖已确认状态，也不能用本次快照缺席自动判定退市。

```bash
.venv/bin/ruff check backend
.venv/bin/ruff format --check backend
.venv/bin/python -m pytest backend -m 'not postgres' -q
```

新增固定模拟值测试覆盖正常、边界、失败和 AKShare fixture 到 Validator 的组合；不访问实时行情。无需新依赖或 migration；本轮不重复前端或 PostgreSQL 升降级测试，开发库和卷保留。
