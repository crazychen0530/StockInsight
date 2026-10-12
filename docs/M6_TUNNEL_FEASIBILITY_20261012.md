# M6 Cloudflare Tunnel 可行性检查：阶段 A / 隔离阶段 B

日期：2026-10-12，Asia/Shanghai。检查基线 `4496600`，分支 `feature/m6-production-deployment`，初始工作区干净。用户决定暂不购买VPS，先检查现有Ubuntu主机与免费Tunnel；仅授权环境/安全预检及无敏感数据的独立Quick Tunnel。**没有授权映射StockInsight业务。** 原[M6验收](M6_ACCEPTANCE.md)保留，失败项不改判，M6-04仍未完成。

**最终状态：阶段A完成；阶段B程序与本机浏览器验证成功，测试入口已关闭，用户蜂窝外网反馈未取得。** 没有以本机浏览器结果替代外网人工验收；需在下次明确测试窗口复验。业务公网阶段不自动启动。

## 1. 阶段 A：主机和运行环境

| 项目 | 本轮只读结果 |
| --- | --- |
| 系统 | Ubuntu24.04.3 LTS，x86_64/amd64 |
| 内核 | 6.6.87.2-microsoft-standard-WSL2；不是独立裸机Ubuntu |
| CPU/内存 | 4逻辑CPU；总7.8GiB、当时可用约2.6GiB，swap8GiB |
| 磁盘 | 当前Linux根卷约1007GiB，总用170GiB、可用786GiB；不等于Windows宿主底层物理余量 |
| Docker | Client/Server29.1.3；Compose2.40.3+ds1-0ubuntu1~24.04.1；Docker active/enabled |
| Git | feature/m6-production-deployment，HEAD4496600；本轮开始干净，不切分支、不commit/merge/push |
| cloudflared | PATH中未安装，未发现用户/系统默认config.yml/config.yaml；没有读取Cloudflare凭据 |

主机只读命令默认沙箱禁止netlink；宿主权限上下文以现有用户UID1000读取Docker和ss，没有使用sudo或管理员密码，没有改防火墙。Docker组本身属于受信任运维权限。本轮未读取需管理员权限的完整防火墙规则或Windows端口转发；不据此断言整台Windows主机不存在外部入口。

### 容器与端口

当时11个运行容器，业务健康检查正常；另有2个已停止的历史验收容器，保持原状。原容器ID、启动时间、restart计数、镜像、发布端口及部署配置哈希保存于本机只读前后快照。

| 项目/容器 | 状态 | 宿主端口 |
| --- | --- | --- |
| stockinsight-local-db-1 | running/healthy | 127.0.0.1:5432→5432 |
| stockinsight-local-api-1 | running/healthy | 127.0.0.1:8000→8000 |
| stockinsight-local-web-1 | running/healthy | 127.0.0.1:5173→5173 |
| stockinsight-local-scheduler-1 | running | 无 |
| stockinsight-m6-db-1 | running/healthy | 无 |
| stockinsight-m6-api-1 | running/healthy | 无 |
| stockinsight-m6-proxy-1 | running | 127.0.0.1:18080→80；127.0.0.1:18443→443 |
| stockinsight-m6-scheduler-1 | running | 无 |
| stockinsight-m6-monitor-1 | running | 无 |
| stockinsight-m6-backup-1 | running | 无 |
| stockinsight-m6-backup-target-1 | running，同机SSH/告警测试接收器 | 无 |

`docker ps`中的5432/tcp、8000/tcp、2019/tcp或443/udp仅可能是镜像EXPOSE元数据，不代表宿主已发布；以HostConfig.PortBindings及ss为准。Caddy admin off，2019不开放。

其他既有监听：SSH的0.0.0.0/[::]:22、loopback3306/33060、1883、DNS53及动态loopback端口。3306/1883对应服务另由进程/服务状态交叉检查；部分动态端口只显示MainThread进程名，未逐一确认用途。非root ss不能显示所有监听进程，未为此索要或使用sudo。本轮不停止、不修改或尝试映射这些服务；SSH通配监听不等于已证明公网可达。

生产DB位于`stockinsight-m6_database`内部Docker网络（Internal=true），无宿主发布端口；开发DB只发布127.0.0.1:5432。Tunnel测试不进入这些网络、不连接数据库。

## 2. 实际代理、TLS与路由

生产为Caddy，仓库`deploy/Caddyfile`，容器`/etc/caddy/Caddyfile`，本轮确认运行文件哈希与源码相同。原生产镜像/Compose不改。

- 当前TLS在Caddy443终止，发布到本机18443，域名localhost，内部CA。只读取公开根CA证书验证TLS，未读取邀请密码、管理员口令或私钥。
- HTTP18080只做301到`https://localhost:18443/...`，无认证但不提供业务内容。不能直接当作公网Tunnel origin，否则浏览器会被导向访问者自己的localhost。
- HTTPS route首先import邀请Basic Auth，随后拒绝POST/PUT/PATCH/DELETE，`/api/*`转发私网API:8000并剥离Authorization/X-Admin-Token；`/docs*`及`/openapi.json`拒绝，其他静态SPA路由回退index.html。
- 页面路径：`/`、`/stocks`、`/stocks/:symbol`、`/guide`、`/source-settings`、`/data-status`。
- API均带`/api/v1`前缀：`GET /health`、`/stocks`、`/stocks/{symbol}`、`/stocks/{symbol}/prices`、`/stocks/{symbol}/indicators`、`/system/data-status`、`/system/source-policy`。完整路由见backend/app/api/router.py及api/v1文件。`PUT /api/v1/system/source-policy`在production后端拒绝，代理也禁写。
- 内部API本身没有全站邀请认证；FastAPI默认docs/OpenAPI/redoc由框架创建，公网保护依赖Caddy入口。绝不能让Tunnel绕过Caddy直接连开发8000、开发Vite5173或生产API。
- 容器内部健康检查直接业务查询/health；若新增公网存活检查，应设计受控探针，不擅自豁免认证。

本轮不带凭据，对首页/搜索/设置/状态/静态路径、API health/stocks/system、docs/openapi/redoc及/.env共13条路径探测，**全部401**；严格CA/主机名验证成功。没有重跑需要邀请密码的认证正向测试，也不将历史结果冒充本轮结果。

## 3. 官方软件来源与出站检查

截至本次检查，Cloudflare官方[下载文档](https://developers.cloudflare.com/tunnel/downloads/)提供Linux amd64独立二进制或官方软件仓库。选择临时独立二进制以避免系统级安装：不apt安装、不修改PATH、不注册systemd、不登录账号。GitHub官方release元数据为2026.10.0，cloudflared-linux-amd64，40,129,756bytes，官方digest SHA-256 `d33ff2d14475178d2012c2c56beba87389ac5ded27649519f198a7d3134a99db`。只在完整下载并校验一致后执行。

官方HTTPS API/包仓库/GitHub可达且证书校验开启；GET api.trycloudflare.com返回405代表服务可达、方法不允许，不代表已创建隧道。region1/region2.v2.argotunnel.com解析成功，各采样2个IPv6地址TCP7844建立连接。系统存在HTTP(S)代理环境变量，只记录变量存在，不保存值。原始UDP send成功不能证明QUIC握手，必须实际Tunnel验证。[官方网络要求](https://developers.cloudflare.com/cloudflare-one/networks/connectors/cloudflare-tunnel/configure-tunnels/tunnel-with-firewall/)为出站7844：QUIC用UDP、HTTP2用TCP；443用于API/下载等。

下载第一次发生TLS EOF，保持TLS校验，有限重试官方资产，不关闭验证、不更换非官方来源。后续通过既有代理完整下载，SHA-256与官方digest一致，运行确认`cloudflared version 2026.10.0`。二进制路径`/tmp/stockinsight-quick-tunnel-1qisi_g3/cloudflared`，不在PATH、不算系统安装。

补充的通用Python IPv4 TLS探测返回SSLCertVerificationError，未关闭验证重试，也不把该探测判为通过；它与官方cloudflared自己的协议/证书处理是不同检查，失败原因未确证。实际cloudflared预检报告两region的QUIC/HTTP2均成功，且真正注册了QUIC连接（见下节），以此证明本轮隧道可用，不用裸TCP成功替代。

## 4. 阶段 B：隔离Quick Tunnel

本轮独立脚本[quick_tunnel.py](../deploy/acceptance/quick_tunnel.py)不导入业务代码、不读生产配置、不连接DB；由内核分配127.0.0.1临时端口，仅`/`、`/health`返回固定JSON，其余404，无文件服务/目录浏览/管理功能。cloudflared使用临时空HOME，metrics也仅loopback，进程最长600秒并支持STOP文件，结束只清理本轮子进程与HTTP服务。

12:41:40实际注册QUIC连接，测试HTTP端口`127.0.0.1:45735`，公网临时地址`https://knows-offerings-ocean-perl.trycloudflare.com`。返回`service=isolated-quick-tunnel-test`、`stockinsight_connected=false`、`test_id=38a271899ac04066a0a52d478781d0ad`。host-side Python严格HTTPS200/正文一致；本机Chromium默认校验证书（ignoreHTTPSErrors=false）浏览器访问200/正文一致。公网负向路径`/api/v1/stocks`、`/.env`、`/docs`、`/unknown`全部404，不能访问业务或文件目录。

仅建立出站隧道，无公网IPv4/路由器端口转发配置、无防火墙或现有端口修改；不声称本次禁用所有已有公网链路作过负对照。日志有ICMP代理因普通用户权限不足被禁用的警告，不影响HTTP测试，不为此改组权限或sysctl。

远端web抓取工具返回“该地址工具不可访问”，没有得到响应，**不算外部验证通过，也不证明Tunnel故障**。已向用户提供手机关闭Wi-Fi、用蜂窝网络访问和检查无证书警告/正文的步骤，在限时窗口等待但未收到反馈；外网人工项未完成，不延长保留无必要后台服务。

最终清理：日志12:52:03显示Tunnel/metrics停止；12:52:35后核验cloudflared本轮PID258452已退出，HTTP45735及metrics45289均关闭，旧公网地址严格HTTPS请求返回**530**，不再返回test_id。初次在最终状态写入前提前检查曾返回“Test still running”，未判通过；待实际退出后重新完整核验得到上述结果。原13容器（11运行/2历史停止）ID/启动时间/restart计数/镜像/端口/网络不变，部署文件及私有env哈希不变，生产DB仍internal。

外部HTTPS需要严格证书验证且响应test_id一致；本机经公网地址GET、工具远端GET、用户手机蜂窝浏览器必须分别记录，不能互相代替。需要用户时提供临时URL与步骤，等待反馈后关闭，不自动保留后台进程。结束还需验证临时本地端口关闭、原公网URL不再返回测试内容。

本轮清理证据见`cleanup.json`、`quic/state.json`、`snapshot-before.json`/`snapshot-after.json`；浏览器证据`browser-probe.json`/截图。临时二进制约38MiB保留在/tmp供受控复验，没有PATH安装或后台进程，后续可删除明确的本轮工具目录；不使用全局清理。复验脚本Ruff/格式通过，既有纯运维单测18passed/0.07s；没有重新执行会创建数据库的后端集成测试。

## 5. 正式映射前检查项（本轮均不实施）

| 项目 | 当前事实、风险与下一阶段要求 |
| --- | --- |
| 全入口认证 | 当前Caddy所有HTTPS入口先Basic Auth，本轮13路径401；后续公开域名/所有方法/编码路径/静态资源/异常路由/邀请撤销需实际复验，不旁路API |
| 调试/管理 | FastAPI内部默认文档存在，代理docs/OpenAPI禁用；redoc走SPA，仍认证。生产策略PUT双层拒绝，正式Tunnel不增加本地管理例外 |
| 敏感信息 | 镜像/静态目录与secret挂载分离，Caddy仅/srv文件服务；本轮不读取或发送凭据。正式验收做受控静态包/日志/响应敏感扫描，API错误不得带连接串 |
| 代理头与客户端IP | 运行uvicorn命令含`--proxy-headers --forwarded-allow-ips '*'`，仅私网入口是现有防线；不保证公网多代理信任链正确。需审定cloudflared→Caddy→API可信来源、剥离伪造头、核验HTTPS scheme/Host/客户端IP与重定向，不信任任意CF-Connecting-IP |
| 前端/跨域/Cookie | Axios相对/api/v1、同源、Vue history fallback适合统一域名；未找到业务Cookie/session、CORS中间件、WebSocket/SSE实现。若加入Access Cookie需验证Secure/SameSite/过期/401页面；未来WS/SSE另测 |
| 三段TLS | 浏览器→Cloudflare边缘TLS，边缘→cloudflared加密隧道，cloudflared→本地Caddy应验证内部CA与SNI，保持noTLSVerify=false。localhost Host/内部CA/301与公开域名不一致；需单独批准域名适配方案，不改原配置凑通 |
| 额外Access | 对2–10受邀用户建议评估Access邮件白名单/MFA和撤销，保留源站Basic Auth或明确替代方案；Tunnel本身不等于访问控制，不能仅靠随机URL |
| 持续运行 | WSL2依赖Windows开机、休眠策略、网络和Docker启动；原Docker enabled不证明WSL自动启动。需批准后测试开机、断电恢复、网络切换、Tunnel重连、外部告警，不在本轮重启主机 |
| 账号/域名/费用 | Quick Tunnel无需账号或域名；正式固定公共hostname按官方文档需Cloudflare账号和托管域名，已有域名可使用，无域名可能需购买，另授权。免费Tunnel不代表域名/备份/电费/付费附加服务免费 |
| 数据与剩余验收 | 行情展示用途仍需确认；真实异地备份/密钥分离与恢复/RPO-RTO、99/100采集失败、15分钟51请求失败仍保留。需分开稳定负载与维护故障窗口再验，不以Quick Tunnel连通覆盖M6失败项 |

以上为源代码和只读运行检查形成的评估，并非已完成正式公网安全测试。官方[origin参数](https://developers.cloudflare.com/tunnel/reference/origin-parameters/)支持caPool/originServerName/httpHostHeader；具体取值需在获批后独立配置与验证，不能用noTLSVerify关闭校验。

[Quick Tunnel官方限制](https://developers.cloudflare.com/tunnel/get-started/quick-tunnels/)：无可用性保证、地址随重建改变、最多200在途请求、不支持SSE，适合本轮测试而非替代正式部署。固定公网应用需[账号和Cloudflare域名](https://developers.cloudflare.com/tunnel/get-started/)；[官方当前免费Zero Trust计划](https://www.cloudflare.com/plans/)用户上限50，首期2–10人可评估免费档，但具体账户资格/限制需用户在注册时确认，未代替用户注册、接受付费或购买域名。

## 6. 复现与清理

只读检查：`cat /etc/os-release`、`uname -m`、`uname -r`、`free -h`、`df -h /`、`docker version`、`docker compose version`、`docker ps`、`ss -lntp`、`command -v cloudflared`、`git status --short --branch`、`git log -1 --oneline`。需sudo时请用户操作；本轮未使用sudo。

Quick Tunnel必须使用已核验官方二进制绝对路径与本轮独立脚本，例如在仓库根目录：

```bash
python3 deploy/acceptance/quick_tunnel.py --binary /tmp/VERIFIED_DIRECTORY/cloudflared --protocol quic --duration 300 --output data/acceptance/m6-tunnel-NEW/quic
```

VERIFIED_DIRECTORY需替换为本机证据中真实路径，output必须是新目录（脚本拒绝覆盖）。脚本会打印真实临时HTTP端口及临时公网URL；不接受用户提供业务origin URL。协议QUIC失败时可在已关闭前一测试后，以不同output目录有限尝试http2。创建对应output/STOP文件可提前清理，或前台Ctrl+C；脚本仅终止自己创建的cloudflared子进程并关闭自己的HTTP端口，不使用pkill、不运行docker stop。停止后再次请求临时URL并核对不再返回固定test_id。

本轮实际命令（验证结束后不应直接重开公网；重做需明确测试窗口）：

```bash
python3 deploy/acceptance/quick_tunnel.py --binary /tmp/stockinsight-quick-tunnel-1qisi_g3/cloudflared --protocol quic --duration 600 --output data/acceptance/m6-tunnel-20261012/quic
touch data/acceptance/m6-tunnel-20261012/quic/STOP
```

## 7. 证据、影响与后续

证据在Git忽略目录`data/acceptance/m6-tunnel-20261012/`，只保存筛选后的运行信息、公开版本/哈希及脱敏日志。新增报告/隔离脚本和6个治理文档保留为未提交工作区变更，暂存区为空，分支/HEAD仍4496600；不提交/推送/合并。原M6验收报告、运行手册及生产配置不覆盖；当前测试进程全停，原服务继续运行，没有DB结构或数据操作。

本轮完成后下一步仅评审正式Tunnel方案、账号/域名/Access、TLS/代理头适配、持续运行和真实灾备，然后等待用户对业务公网开放的新确认。无需购买VPS，也不自动注册账号、购买域名或使用生产token。


### 隔离测试重新开启（2026-10-12 13:12，Asia/Shanghai）

用户明确要求“重新开启”。复查原11个运行容器仍在运行、原业务端口保持loopback，旧测试进程不存在；官方临时二进制SHA256复核一致。使用原隔离脚本及独立新证据目录 `data/acceptance/m6-tunnel-20261012/quic-retry-1/`，不覆盖首次证据。新服务仅127.0.0.1:46191固定JSON，QUIC已注册，主机侧严格HTTPS返回200且正文一致。临时URL为 https://anyone-missing-drew-syndrome.trycloudflare.com ，test_id=e640da55f33c489ca626285fe2ba7eac；已说明手机热点情景可以验证，等待手机蜂窝浏览器实际反馈，不能预先标为通过。窗口最长600秒，约13:22自动清理；收到反馈可通过该目录STOP文件提前清理。业务映射未授权，本轮无系统安装、生产配置/数据库操作及Git提交。最终外网反馈与清理情况以后续补记为准。


### 重新开启窗口最终结果（2026-10-12 13:14，Asia/Shanghai）

用户明确反馈手机访问“访问成功，内容一致，无证书警告”，阶段B人工外网浏览器验证完成。收到反馈后写入本轮证据目录STOP文件，脚本实际退出0；13:14:30核验owned_process_alive=false、local_port_closed=true，临时公网URL返回HTTP530且不含测试test_id，确认入口已失效。原11个运行容器仍在运行、API/DB/web健康，业务loopback发布端口保持原状。未操作原服务、数据库、生产配置或Git提交；测试二进制文件保留/tmp，测试进程不保留。证据在data/acceptance/m6-tunnel-20261012/quic-retry-1/state.json及cleanup.json。TASKS仅将阶段B人工外网子项更新DONE，首次窗口未反馈证据不覆盖，M6-04和真实异地备份/混合维护失败项不变。后续仅评审StockInsight正式映射前置条件，等待用户单独确认，不自动开放业务。
