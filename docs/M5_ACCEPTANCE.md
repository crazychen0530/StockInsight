# M5 发布候选验收记录

验收日期：2026-10-12（Asia/Shanghai）。本轮范围为真实本地采集、独立自动更新及 M5-01～05；不包含 M6 公网部署、交易或数据再分发。

## 1. 真实业务链路

- 股票目录：5,223 只支持范围内沪深 A 股，真实 `stock_info_a_code_name`；CDR 与北京股票排除。
- 实际日线覆盖：`000001.SZ` 平安银行、`600519.SH` 贵州茅台、`300750.SZ` 宁德时代、`600036.SH` 招商银行，各 183 条，共 732 条；2026-01-05～2026-10-09。目录数量不是行情覆盖数量。
- 持久来源 `akshare_tx`，腾讯不复权、人民币元/股/元、UTC 获取时间；当前最新已收盘交易日为 2026-10-09，本次运行时 10 月 12 日尚未开盘。
- 同事务生成 732 条 `sma-close-v1` 均线；贵州茅台最后 MA60 `1291.0760`。不足窗口为 null，不编造历史。
- 真实 Chromium 搜索→详情→K 线 SVG→MA5/20/60→实际来源与时间→状态页，桌面与 390px 手机通过。`frontend/scripts/browser-live.mjs` 不拦截请求、不使用 fixture。
- Compose `automation` profile 独立进程、17:30 上海时区、启动补最近收盘日、有界重试与持久成功防重；常驻容器已运行，重启后 `job_count=0, skipped_jobs=4`。今日实际 17:30 尚未到，未冒充已经发生的未来定时触发；时区/跨日触发另有确定性测试。
- 2026 全年日历按交易所公告显式生成，242 天、覆盖至 12-31；覆盖外拒绝执行。目录未逐行保存来源时间，股票详情仍如实显示未记录。

初次真实采集暴露并修复：CDR 混入；Pandas JSON 浮点尾数；腾讯 SDK 金额单位换算尾数；AKShare 1.19.1 深市 000 股票手/股缺陷。东方财富日线接口在本网络连续失败，显式配置腾讯后成功，不自动改源。保留真实失败任务及错误码，不用模拟数据清洗验收结果。

## 2. M5-01 十类测试证据

| 类别 | 实际验证 | 结果 |
| --- | --- | --- |
| Provider 契约/隔离 | fixture 字段、CDR、腾讯单位、精度、SDK 子进程超时/日志抑制 | 通过 |
| 输入与存储边界 | Validator 代码、日期、重复、OHLC、Decimal、BigInt | 通过 |
| 数据库持久化 | 股票/日线 UPSERT、整股事务、回滚、跨股部分成功及并发 | 通过 |
| CLI/恢复 | 实际 CLI 子进程、失败恢复、SIGTERM/SIGKILL、防重/幂等 | 通过 |
| API | 六个 GET、分页/区间/上限、只读一致性、错误脱敏 | 通过 |
| 纯指标 | MA5/20/60、窗口不足、乱序、无未来数据、确定精度 | 通过 |
| 指标集成 | 行情与指标同事务、历史插入/修正、全历史重算与并发 | 通过 |
| 调度 | 上海时间/日历/就绪/缺覆盖、有界重试、补齐、重启防重 | 通过 |
| 前端/浏览器 | 类型、31 组件测试、构建；模拟边界与真实数据浏览器分开验收 | 通过 |
| migration/部署恢复 | 六个新隔离库内升级/降级/再升级/模型一致性；独立恢复 HTTP | 通过；全新 Linux 见下一节 |

实际命令：`.venv/bin/python scripts/test_postgres.py` → **388 passed in 15.79s，无 skip/deselected**；`.venv/bin/ruff check backend scripts/backup_postgres.py`、格式检查通过。前端 `npm run typecheck`、`npm test` → **31 passed**，`npm run build` 通过；`npm run test:browser` 模拟空/错/重试/缩放/手机通过，真实页面脚本独立通过。

本机真实 API 每项顺序查询 20 次：搜索 p95 17.83ms、日线 30.59ms、均线 32.42ms、任务 8.02ms；这是当前样本与本机延迟，不是并发负载容量承诺。图表 chunk 602.26KB（gzip 206.73KB）保留 Vite 警告，已复核本机首屏可用，后续公网优化属于 M6。

## 3. M5-02 全新 Linux

**通过。** 官方 Ubuntu Minimal 24.04 镜像 SHA-256 已校验，独立 QEMU TCG 虚拟机 Ubuntu 24.04.5、内核 6.8.0-146-generic，独立 Docker29.1.3/Compose2.40.3。最初 Images=0、Containers=0、零既有卷；不共享宿主 Docker socket。按 README 预构建开发镜像部署路径导入当前制品和无私有配置/无数据源码包，初始化新 .env、新卷、启动、迁移。迁移 head `0001_initial_schema`，`alembic check` 无新操作，采集前四表实测 `0|0|0|0`。

先独立采集 5,223 只股票和贵州茅台 183 条真实日线/指标，随后新环境的独立 scheduler 实际完成 4 项更新，最终 `5223|732|732|6`。Vite 代理的搜索、日线、均线、状态四项 HTTP200，真实 Chromium 桌面/390px 及健康调整后复验全部通过，最后 MA60 `1291.0760`。三服务最终均 healthy，scheduler 正常运行；没有导入原开发库行情或 fixture。最终新 Linux 调度重启后 `job_count=0, skipped_jobs=4`；49 个后端运行源码文件及21个前端源码文件的聚合SHA-256与原工作区一致。

实际遇到并处理：SSH stdin 被交互 Docker 命令消耗，改为上传脚本文件执行并关闭交互；上游直连失败，原任务按有界重试失败后，核验本机代理 URL 无认证信息，只传入无凭据 host/port 地址并恢复原任务。未转移代理凭据。TCG 缺少 KVM 加速导致采集高峰探测进程启动过慢；仅该验收环境叠加 `compose.acceptance.yaml`，预算30秒/间隔15秒，原 HTTP 探测保留，另用真实 API/浏览器证明功能。普通开发环境仍是5秒探测预算。此演练验证新 Linux 部署，不以软件模拟耗时评估生产容量。

## 4. M5-03 安全、依赖与授权复核

- 后端运行时/开发/采集依赖版本写入 `backend/constraints.txt`，前端 `package-lock.json`；Python 3.12 与 Node 22 固定大版本。
- 独立临时审计环境执行 `pip-audit -r <已安装完整依赖清单> --no-deps --disable-pip -f json`：无已知漏洞；`npm audit --json` 在 TLS 证书验证开启时重跑：0 漏洞（229 个依赖节点）。结论限于此次审计数据库，非未来保证。
- Docker 构建代理仅用 BuildKit secret，不进入 build args 或镜像层；一次可能持久化代理的请求被自动审批拦下，未执行，已采用临时 secret 的安全方式完成后端构建。
- db/API/web 仅 loopback 5432/8000/5173；独立恢复实例仅 loopback 15432。API 只读，无管理写入入口；开发库超级用户为本地用途，生产最小权限账户与认证属于 M6，不能直接公开本开发 Compose。
- 行情单位、不复权、来源、获取时间、指标版本和窗口不足均可见；全局免责声明不构成投资建议，不下单、不保证收益。
- [AKShare MIT 许可](https://github.com/akfamily/akshare/blob/main/LICENSE)只适用于 SDK，不证明上游行情授权。[东方财富免责声明](https://about.eastmoney.com/home/disclaimer)明确提示转载权限要求；腾讯数据公开展示/商业再分发许可未取得。因此本次仅本地个人研究，M6 公网展示与商业使用仍须所有者确认上游授权。复核已完成，不将缺少公开许可冒充已获许可。
- 密钥、真实 `.env`、私钥、日志与备份不进 Git；最终提交前再做实际私有凭据比对、模式扫描与差异检查。

## 5. M5-04 备份恢复

已从开发库 `pg_dump -Fc --no-owner --no-acl`，GPG AES-256 加密归档，解密直接通过内存/管道恢复，明文归档未落盘。密钥 `secrets/backup.passphrase` 0600，归档 `data/backups/stockinsight-20261011T172650Z.dump.gpg` 0600，两者均忽略。

独立 PostgreSQL 16 容器 `stockinsight-m5-restore-1bdd7e`、独立卷、loopback 15432，恢复后：revision 1 行、stocks 5,223、daily_prices 732、technical_indicators 732、data_sync_jobs 13。逐表完整内容 SHA-256 相同；约束与索引规范化反解析的等价 text cast 后相同。恢复后临时 API 8002 的搜索、股票详情、183 条行情、183 条指标与任务状态全部 HTTP 200，临时 API 已停止。

原库后来启动常驻调度新增任务，因此原库当前任务数可以大于备份时 13，不是恢复丢失。没有删除或覆盖原开发库、测试库和数据卷。仓库 `scripts/backup_postgres.py` 的实际加密备份命令也已成功执行。此为本地恢复演练，不是异地备份、轮转或生产 RPO/RTO 验收。

## 6. M5-05 发布候选与剩余边界

**M5-01～05 全部通过，v0.1.0 发布候选准备完成。** 实现、十类测试、真实采集/调度、独立新 Linux、审计、加密备份恢复和文档已核对。v0.1.0 版本号既有，本轮不创建 tag/Release、不推送或公网部署。M6 另需明确公网需求、授权、生产配置与容量评估，目前无需购买服务器。

证据副本位于本机 Git 忽略目录 `data/acceptance/m5-20261012/`，含真实浏览器截图、完整后端测试、依赖审计 JSON、四股日期/均线复核、性能及恢复报告、新 Linux 运行记录。不是对外发布的数据包。临时验收 VM 和恢复实例验收后正常停止，保留磁盘/卷；原开发环境三服务与 scheduler 继续运行。
