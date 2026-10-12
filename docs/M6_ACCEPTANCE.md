# M6 生产部署与本地验收

日期：2026-10-12，Asia/Shanghai。基线 `157c01c`，分支 `feature/m6-production-deployment`。用户要求运行整个 M6，并回复暂无服务器、域名、异地备份目标。

**M6-01～03 的实现和本地演练完成，M6-04 公网部署待资源。整个 M6 尚不能标记完成。** 没有采购、创建远程资源、开放公网、push、tag 或 Release。命令见 [生产运行手册](M6_PRODUCTION_RUNBOOK.md)。

## 1. 实现与安全

独立生产镜像/Compose、Caddy 静态前端与同源代理、HTTPS、逐人邀请认证/撤销、全站/API认证、生产只读页面与双层禁写、私有数据库、四类最小权限账户、显式 migration、进程监督、资源上限、日志脱敏轮转、监控及 HTTPS 告警、每日加密 SSH 备份、本地7日/4周保留、空库恢复和同 schema 镜像回滚均已实现。

没有业务 Schema/数据口径/指标算法或核心栈变化；调用分层、独立 scheduler、每股幂等/失败保留沿用原有逻辑。静态页不含数据库或管理口令。Caddy/运维是既有单机生产拓扑的落地，ADR-022 Accepted（此次用户执行整个M6的授权）。

开发项目 `stockinsight-local` 与原卷保持独立，仍为本机5432/8000/5173。新项目 `stockinsight-m6` 只绑定本机18080/18443；没有 DB/API 发布端口。数据/私钥/凭据/证据均在 Git 忽略目录，不进提交。

## 2. 真实行情与容量

初始从开发库只读快照复制目录/行情/指标到新库，未复制原同步任务。开发库未被100股采集改写。私有生产名单使用 [100股容量样本](../config/universe/preview-100.json)：原4股加目录升序96股；采集起点2026-01-05。不声称这是最终业务自选股。

- 串行单批 **5分50.378819秒**，100项任务，**99成功、1失败**。
- 失败 `000016.SZ`：`daily_data_not_ready`，目标2026-10-09未就绪；不推断停牌/上市状态，不删除失败或悄悄移出名单。
- 日线与指标各 **18,106行**，实际覆盖99股；真实腾讯 `akshare_tx`、不复权、既有单位/UTC获取时间。目录5,223股不等于全市场日线。
- 开发环境仍4股各183行、日线/指标各732行；测试并未扩采原库。

宿主4逻辑CPU/7.76GiB；M6常驻服务限制到CPU集合0,1，并分别设置数据库1GiB、API512MiB、scheduler1280MiB、proxy256MiB、monitor128MiB、backup256MiB上限。各容器上限不构成整台机器4GiB隔离；本机其他服务仍竞争资源。单次并发期快照 db76.77MiB/API67.56MiB/proxy16.12MiB/monitor14.70MiB，不是峰值；目标2核4GiB VPS还需实际复验。

## 3. 验收记录

| 项目 | 实际执行与结果 |
| --- | --- |
| 后端全量 | `.venv/bin/python scripts/test_postgres.py`：六个新隔离库，**399 passed in13.33s**，包含既有migration/采集/调度/API；未清已有库 |
| 运维逻辑 | `.venv/bin/python -m pytest deploy/tests -q`：**18 passed**，含空库/独立库恢复门禁、保留策略、日历边界、SSH路径/远端校验失败、公网配置门禁、schema变化拒绝回滚 |
| 静态检查 | `.venv/bin/ruff check deploy scripts` 与 `ruff format --check deploy scripts` 通过 |
| 前端 | Node22 `npm run typecheck`、`npm test` **39 passed**、生产镜像内 `npm run build` 通过；原详情大chunk提示仍存在 |
| HTTPS/认证 | `scripts/verify_production.py`：**11项通过**，严格信任演练CA/验证主机名，HTTP301到正确HTTPS端口，全站未认证401、认证200、SPA回退、写403、docs/OpenAPI404 |
| 邀请撤销 | 新增colleague认证200，撤销并重建proxy后colleague401，原preview仍200；未输出密码 |
| 数据库权限 | API可SELECT不可INSERT/UPDATE/CREATE，worker可INSERT不可DELETE，backup可SELECT不可UPDATE；实际API UPDATE被PostgreSQL拒绝，表owner为si_owner |
| 混合负载 | `scripts/load_production.py --seconds 900`，10用户、100股轮询、3次GET/旅程+1秒思考：**901.02秒、26,019次、51失败（0.196%）、成功请求p95 19.52ms**。期间存在采集/备份/邀请撤销及proxy重建；严格零错误脚本退出1，保留为含维护影响结果，不标成零错误通过 |
| 稳定状态复验 | `.venv/bin/python scripts/load_production.py --seconds 60`：10用户、60.92秒、1,725请求、**0失败、p95 38.64ms**，脚本退出0。此为60秒复验，不冒充15分钟零错误 |
| 生产浏览器 | Node22 `node scripts/browser-production.mjs`：真实数据搜索→K线/均线、只读表单隐藏、失败任务可见、教程、桌面/390px手机通过，无pageerror/手机横向溢出；截图已目视复核 |
| 告警 | 未就绪股票触发market_data_stale；本地无公网域名触发tls_monitor_unconfigured。专用HTTPS接收器实际收到告警JSON；不是只验证配置存在 |

备份/恢复/回滚/最终浏览器与稳定状态结果见下节和本机证据。公网证书、外部可达性和接收人的人工确认尚未完成。

## 4. 备份与恢复

第一次严格 SSH 传输备份81,723bytes，1.351秒；对端SHA-256一致。恢复到新 `stockinsight_m6_restore`，0.217秒，stocks5223/daily_prices732/indicators732/revision一致，三表逐行规范化SHA-256一致。

扩采后再次备份 **658,732bytes/1.681秒**，远端哈希一致；恢复到新的 `stockinsight_capacity_restore` **0.422秒**。`deploy/acceptance/verify_database.py` 验证四表行数与内容SHA-256完全一致：5223/18106/18106/100，revision0001_initial_schema，权限符合预期。源库pg_database_size **15,875,095bytes（15.14MiB）**，实际覆盖99股。

SSH接收端为同机独立容器/卷，无宿主端口；known_hosts严格校验、专用密钥、不关闭TLS或SSH校验。它验证传输协议及完整性，**不算异地故障隔离**。生产需要不同机器/存储账户/故障域。测试HTTPS回调使用专用受信CA；浏览器UI验收单独允许本地证书，严格TLS证明来自Python验证。

错误备份口令演练退出1，之前成功回执未被覆盖，没有残留partial归档，HTTPS接收器实际收到backup_failed。恢复只写新空库；未覆盖开发或演练生产库。保留策略及远端哈希错误不得转正式文件已测试。远端为追加策略，异地管理员负责保留和容量，不宣称远端自动清理。

RPO24h/RTO2h为生产目标；上述秒级耗时只覆盖本地数据传输/恢复步骤，不包含主机重建、密钥取回、下载、DNS切换或人工验证。

## 5. 发布、回滚与证据

release 记录发布前schema/旧镜像ID，备份后migration，启动后核心查询；prepared与completed状态明确分开。rollback在schema不变时恢复镜像，并保留新的私有rollback env；schema变化必须独立恢复。

实际故障演练：专用overlay将M6 API命令替换为退出1的Python进程；按发布回执 `20261012T032539Z-72bc6985.json` 回滚，核心查询及原10项HTTPS检查全部恢复通过。随后重新发布最终镜像，`20261012T032825Z-0358b258.json` completed；production scheduler与每日backup常驻，开发项目不受影响。scheduler启动跳过99成功股、重试失败股仍未就绪，失败可见，不宣称未来17:30定时触发已验证。

本机证据 `data/acceptance/m6-production/`（Git忽略）：后端日志、collection-100.log、load-15min.json、权限/恢复内容哈希、加密备份回执、release/rollback日志、桌面/手机截图。发布清单位于 `data/releases/`；备份在独立Docker卷，密钥在secrets/production。需要审计时通过本机受控方式读取，不提交密钥或原始日志。

## 6. 待公网完成

M6-04保留TODO（缺资源）。需要目标服务器及SSH、真实域名/DNS、异地SSH目标与可信known_hosts、HTTPS告警接收通道/运维负责人、行情展示用途确认、最终名单。随后在目标地区核验上游可用性、100股采集、实际2核4GiB资源、持续10用户、有效公网证书/续期/外部存活监控、真实异地恢复及回滚。预算仍未批准；价格参照保留M6-01报告日期，不当作本次采购报价。
