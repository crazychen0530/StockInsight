# 数据源连接诊断与替代方案

## 当前结论（2026-10-12，Asia/Shanghai）

东方财富当前可获取，无需用户账号：直连和环境代理对贵州茅台、平安银行均 HTTP200，各183条；项目原有 Provider → Validator 及腾讯对照均通过，区间2026-01-05～10-09。scheduler容器内东方财富同两样本各183条也通过。本轮未修改业务适配器、未升级SDK，不能将此前的网络失败归因为已证实的登录/限流问题，也不能保证未来可用性。

[AKShare官方实现](https://github.com/akfamily/akshare/blob/main/akshare/stock_feature/stock_hist_em.py)直接请求`https://push2his.eastmoney.com/api/qt/stock/kline/get`，`secid`指定市场/股票，`klt=101`为日线，`fqt=0`为不复权，`beg/end`为日期；固定`ut`并非用户登录Token。请求没有用户账号、密码或登录Cookie。

## 只读复现

从仓库根目录、已安装market-data extra的虚拟环境运行：

```bash
.venv/bin/python scripts/diagnose_market_data.py --symbol 600519.SH --start 2026-01-05 --end 2026-10-09
.venv/bin/python scripts/diagnose_market_data.py --symbol 000001.SZ --start 2026-01-05 --end 2026-10-09
```

每次只有四项探测，不自动重试、不写数据库：东方财富HTTP直连、HTTP使用当前环境代理、东方财富Provider与Validator、腾讯Provider与Validator。网络探测connect/read超时为6/12秒，SDK子进程总超时45秒。默认验证TLS；不打印响应正文、代理地址、原始异常或凭据。直连Session不读取环境代理及环境CA设置，环境模式按requests正常读取；企业CA差异也可能导致结果不同。退出0要求两个Provider均返回非空合法数据；HTTP单独失败但Provider成功时仍需看逐项结果。未注入官方日历，校验通过不单独证明区间交易日完整。

排查顺序：

1. 直连成功/环境失败：检查本机代理及`NO_PROXY`，不要将宿主`127.0.0.1`代理地址原样传给容器。
2. 环境成功/直连失败：定位网络出口、DNS或TLS路径，使用已验证可达的正常网络配置；不关闭证书校验。
3. HTTP成功/Provider失败：按`provider_timeout`、`provider_contract_error`区分子进程导入/响应字段/精度问题；空结果不能当成功覆盖。
4. 两条HTTP均失败：保留HTTP状态和异常类型，稍后少量复测，避免高频重试；429/403本身也不能证明需要登录。
5. Provider成功/任务失败：检查数据库、任务锁、日历和当日行情就绪。`scheduler_storage_error`属于存储路径，不是行情接口错误。

## 来源选择

| 方案 | 当前状态 | 适用与代价 |
| --- | --- | --- |
| AKShare腾讯 `stock_zh_a_hist_tx` | 本项目已集成；本轮沪深真实样本通过，Compose默认 | 当前本地研究继续使用；同样依赖上游网页接口，无长期可用性保证 |
| AKShare东方财富 `stock_zh_a_hist` | 已集成；本轮完整链路通过 | 可显式切换；本轮不足以证明它长期优于腾讯 |
| Tushare Pro `daily` | 官方文档已核对；未集成、未实测 | 有明确Token及权限/频率体系，适合后续批量日线需求；需账号权限评估和新Provider适配 |

[Tushare日线文档](https://tushare.pro/document/2?doc_id=27)、[Token说明](https://tushare.pro/document/1?doc_id=40)、[权限频率表](https://tushare.pro/document/2?doc_id=290)。接入时需统一成交量/金额单位、保留来源与时间、通过现有Validator；不把文档支持视为本项目已接入或性能保证。

现有Compose通过`.env`的`MARKET_DATA_DAILY_INTERFACE`显式选择来源：腾讯为`stock_zh_a_hist_tx`，东方财富为`stock_zh_a_hist`。如需持久切换，先备份私有配置，改该变量后重建scheduler容器配置：

```bash
docker compose --profile automation up -d --no-build --no-deps scheduler
```

切换不清库，但之后重采重叠日期会按现有UPSERT更新行情来源并重算均线。成功任务的防重不会因来源设置变化而自动重跑；需重采时使用[受控CLI](COLLECTION_CLI.md)。本轮保持腾讯常驻，不静默回退、不覆盖现有行情。历史失败任务仍保留。

如Docker或宿主重启后数据库/API/web退出，可用`docker compose start db api web`恢复原容器和原卷；仅scheduler配置了`unless-stopped`，不将它当作整个服务栈自动恢复保证。
