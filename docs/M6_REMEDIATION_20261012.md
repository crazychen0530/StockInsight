# M6 剩余问题处理记录（2026-10-12）

用户决定暂不合并，先处理剩余问题；明确授权股票目录、日线K线、均线及任务/来源状态通过运行时trycloudflare.com地址匿名公开8小时。原保护要求与原M6失败证据保留。本记录区分修复候选、正在运行的旧版本及真实部署验收。

## 当前状态

| 项目 | 结果与边界 |
| --- | --- |
| 匿名公网 | 19项公网门禁、严格TLS桌面/手机浏览器搜索/K线/均线通过；用户手机反馈“正常”。窗口北京时间23:37:08到期，到期清理尚待实际核验 |
| 000016.SZ缺目标日日线 | 原因已确认；有限停牌调度/监控修复已获授权，仅更新scheduler/monitor并补采158条真实历史；100股有历史，日线/指标各18,264行；后端407/运维22测试通过。原失败任务保留 |
| 维护中访问失败 | 独立匿名代理USR1热加载已实现；15分钟10读者/3次真实配置变化：900.84秒、26,037请求、1次连接异常、p95 16.81ms；严格零失败未通过。原混合维护51次失败不改判 |
| 异地备份与RPO/RTO | 仍缺真正不同故障域目标，同机SSH测试不是异地；不得标通过 |
| WSL长期运行与恢复 | 未做关机/休眠/断电演练，需用户提供维护窗口及Windows电源操作 |
| Git | 用户后续接受限制并授权；功能首版已快进合并main至ad38557并推送origin/main，远端SHA核验一致 |

## 停牌原因与修复

[康佳2026-88官方公告](https://disc.static.szse.cn/download/disc/disk03/finalpage/2026-09-28/28069408-51ea-40c2-b87a-9e12d0126af4.PDF)确认9月4日起停牌，并说明现金选择权申报阶段不再交易，申报期至10月13日。登记区间仅覆盖2026-09-04～2026-10-13；届满须重新核验公告，不能无限期屏蔽数据陈旧告警，不据本公告推断最终退市完成。

无数据库连接的隔离候选容器真实上游检查：腾讯akshare_tx返回158根不复权日线，2026-01-05～2026-09-03；按公告计算的预期日9月3日通过ReadyProvider严格日历/尾日检查。证据data/acceptance/m6-remediation-20261012/real-provider-check.json。

实现位于[登记器](../backend/app/jobs/trading_halts.py)、[调度器](../backend/app/jobs/scheduler.py)、[监控](../deploy/operations.py)及[公告登记](../config/calendars/stock_halts.json)。只调整已核验停牌区间内单股应有的最后交易日期；不补虚构K线，不改变复权、单位、指标或Schema。调度生成新的历史日期scope，保留原目标日failed任务；集成测试逐列验证旧失败行不变、真实交易日写入、停牌日无伪造行、重复tick不再采集。监控仍将缺历史、其他股票陈旧和公告覆盖范围外日期判为陈旧。当前两后台服务已加载修复，补入真实历史后数据陈旧告警消除；旧失败任务与原验收失败证据保留。

## 修复部署（已获针对性授权并执行）

候选镜像从本机旧版依赖镜像派生，新标签不覆盖旧标签；构建禁用网络，不安装系统软件。最终app镜像ID以1fe17c03f466开头，ops以e05b8a94b1e3开头；完整ID及代码SHA256位于data/acceptance/m6-remediation-20261012/candidate-manifest.json。运维镜像使用Python3.11，首次导入实测暴露旧验证器的Python3.12语法依赖，已改为纯标准库登记器并在最终镜像离线导入通过。

[候选overlay](../deploy/compose.halt-monitor.yaml)仅覆盖scheduler/monitor镜像和配置挂载；独立候选scheduler配置位于data/runtime/halt-scheduler.json，原私有scheduler.json不改。非敏感候选env保存完整镜像ID；Compose config --quiet已通过。

用户先询问含义，未视为授权；解释后明确回复“可以执行更新”，针对性允许仅scheduler/monitor重建、使用已有最小权限凭据正常补采。16:01完成两服务更新，保留原告警SSL_CERT_FILE和只读CA挂载；API、原代理、数据库与开发容器均未替换。原私有scheduler.json及.env不改，使用单独配置。没有调用全量release或migration。

实际更新命令如下（已执行，不要为重复启动再次重建；日常使用根目录start）：

```bash
# 保留已有本地验收告警CA overlay；仅更新两个获准服务。
docker compose --env-file .env.production --env-file data/runtime/halt-candidate.env -f compose.production.yaml -f deploy/acceptance/transport.compose.yaml -f deploy/compose.halt-monitor.yaml --profile automation up -d --no-deps scheduler monitor
# 随后检查新调度任务、原失败行保留、000016最后真实交易日、监控及原HTTPS。
python3 scripts/verify_production.py
```

如需回退，使用原.env.production和原compose.production.yaml，并保留原transport告警overlay，仅恢复scheduler/monitor；不删除新增真实历史，不删旧失败行，不做schema回退。回退会改变两容器ID，另记证据。日常stockinsight.sh start只启动现有容器，保持本次镜像；不要清理data/runtime/halt-scheduler.json及halt-candidate.env，后续Compose维护需显式带本次overlay以免退回旧版。

实际数据库核验：100股有真实历史，日线与指标各18,264行，000016为158条、尾日9月3日；任务共101条，新历史scope成功，旧10月9日failed任务仍保留。schema版本仍0001_initial_schema。重复--once返回0任务/0失败/跳过100，101个任务逐字段不变。公网匿名严格TLS请求该股得到158条；原HTTPS/认证/只读11项仍通过。monitor重跑只剩tls_monitor_unconfigured，market_data_stale消除，退出1属于仍有TLS配置告警而非“全部运维通过”。

更新前完整快照辅助查询失败，组合shell命令未按预期停止，仍继续执行了已授权的更新；已明确告知用户。失败原因事后确认为辅助JSON解析只取第一行，而json_agg(composite)输出多行，不是权限不足或数据库损坏；拆分/紧凑jsonb查询成功。**缺少首次更新前旧任务逐字段快照**，不能补写该证据；运行时证明旧failed仍存在、重复tick不改101行，逐字段保留行为另有隔离集成测试证据。后续命令统一set -e。更新前已有同机严格传输备份回执为11:30（03:30UTC）、remote_verified=true，不冒充异地或本次新增数据已备份。

16:07实际核验仅获准两个容器ID改变，其他11个原容器/原配置哈希完全不变，DB仍Internal=true，原告警CA保留。回执在update-protection.json、database-after-checks.json、jobs-after.json、idempotency.json及public-halt-query.json，均Git忽略。

## 临时代理热加载验证范围

新public-reload只对匹配owner标签的临时匿名Caddy操作：验证候选配置、原子替换目录挂载文件、USR1热加载；不开放管理HTTP接口。[Caddy官方信号说明](https://caddyserver.com/docs/command-line#signals)说明USR1可重读run启动配置。测试交替改变Cache-Control的max-age=0，实际核验响应头生效、容器ID/PID/StartedAt/RestartCount不变。轮询公开目录前100股（并非与原生产100股名单完全相同），每旅程3个API请求，1秒思考，10客户端900秒。

这仅覆盖新匿名代理配置维护；不包含原邀请撤销、API镜像替换、采集及备份并发的全部原混合场景。原51失败缺逐请求状态/维护事件时间线，不能断言全部由proxy重建造成。load_production新增status_counts，原认证模式默认行为保留。原M6_ACCEPTANCE.md与M6_PRODUCTION_RUNBOOK.md不覆盖、不改写。

本轮实际结果900.84秒、26,037请求，26,036个HTTP200、1个连接异常status=0，成功请求p95 16.81ms，脚本退出1。三次热加载在60.50/300.50/600.58秒确认响应变化，容器ID/PID/start/restart均不变；finally恢复新配置源文件并再热加载成功。不能标记维护零失败通过；该次异常缺类型/时间，不能断言根因。已补充脱敏error_samples（最多20条，只记异常类、底层原因类、相对时间和无敏感的查询路径），不打印异常原文、凭据或头；90秒密集热加载诊断完成，另目录保留证据：90.69秒/2,610请求/3次RemoteDisconnected/p95 21.89ms，异常位于3.335/51.330/84.352秒，与3/51/84秒的热加载对应。28次热加载配置均生效且容器进程不变，最终源文件恢复。说明此主机Caddy2.11.7的当前热加载流程仍会使少量连接在收到HTTP响应前断开；时间关联已复现，但尚未定位到Caddy/Go内部代码，不声称已证明内部根因。没有加入自动重试来掩盖严格验收错误。

后续处理方案待评审：简单维护窗口接受短暂中断，或设计固定入口加双实例、健康检查和排空的滚动维护。后者涉及部署拓扑，不能在用户询问停牌修复含义时自动实施；仍须在完全隔离环境复现原混合场景，保留逐请求错误与维护事件时间线。当前不能承诺维护零中断。

## 公网与清理

当前URL：https://programmer-lectures-expert-epa.trycloudflare.com 。本轮8小时从15:37:08至23:37:08；不延长已授权窗口，不自动续期。前次审批拒绝后取得具体数据/目的地确认，新审批通过才执行。初次匿名日志空字符串脱敏、tmpfs CA读取、目录权限和出站探测故障均保留独立失败证据；公网探测固定IPv4、严格证书、有限重试/超时，状态记录curl退出码，不将网络波动误写为安全门禁通过。

```bash
cd /home/crazychen/myprojects/StockInsight
./stockinsight.sh start        # 仅恢复现有本地服务
./stockinsight.sh public       # 新开8小时匿名只读窗口，保持终端和主机在线
./stockinsight.sh status       # 另一终端查看状态
./stockinsight.sh public-stop  # 提前关闭自己的临时入口
```

到期/STOP/Ctrl+C仅清理本轮Tunnel与临时匿名代理，不停止原服务。当前窗口仍在运行，未来清理不得预记通过。旧带认证窗口process_stopped=true且PID不存在，外部复核遇URLError及curl DNS失败，保留未确证的外部HTTP状态，不声称530。

## 外部资源与人工验收

暂不需要买VPS；Quick Tunnel本轮不需自有域名、Cloudflare账号或付费资源，临时域名不提供长期可用保证。真实异地备份可使用用户已有独立SSH主机/独立存储，不强制采购；需可信主机指纹、专用低权限账户、加密密钥离线管理和恢复演练。无资源时明确BLOCKED。长期运行需用户安排Windows休眠/关机策略与恢复测试、确认主机在线、Tunnel重连、外部告警实际接收人。正式固定域名/账号/Access另行评审，不自动采购或设置系统服务。
