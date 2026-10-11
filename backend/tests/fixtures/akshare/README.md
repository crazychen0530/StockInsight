# AKShare 离线契约 fixture

这些是人为构造的模拟数据，仅验证字段、日期、单位和错误边界。代码用于验证 SH/SZ/BJ 映射，名称与价格不代表对应证券真实信息；不得导入开发行情库或作为真实样本展示。

字段结构依据 2026-10-11 查阅的 [AKShare 官方股票接口文档](https://akshare.akfamily.xyz/data/stock/stock.html)。`daily.json` 中成交量是上游单位“手”，成交额是元。JSON 使用 DataFrame `orient="split"` 的 columns/data 结构；省略适配器不使用的 index。
