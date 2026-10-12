# M6 现有主机限时业务公网试用

日期：2026-10-12；用户明确授权“业务公网试用”。这是阶段A/B完成后的新增授权，原可行性报告中的“未授权”描述保留为历史事实。基线feature/m6-production-deployment /4496600，保留已有未提交工作区，禁止自动commit/merge/push或采购。

## 方案与边界

使用现有官方校验过的/tmp独立cloudflared2026.10.0，QUIC Quick Tunnel，最长3600秒。入口指向https://localhost:18443原Caddy；originServerName和httpHostHeader均localhost，origin-ca-pool仅公开CA证书，未启用noTLSVerify。不指向开发8000/5173、私网API或数据库，不修改原Caddy/Compose/生产环境文件，不重启、重建或停止原容器。浏览器到边缘、隧道及源站HTTPS三段均受保护；Cloudflare处理边缘TLS请求。本轮不注册账号、不购买域名、不启用Access、不安装系统软件。

邀请Basic Auth覆盖页面/API/静态文件，生产只读限制保留。操作员验证在内存读取现有preview邀请密码，用户名preview；不记录或回显口令，不把口令放到URL/命令行或浏览器追踪文件。该账号用于所有者本轮验证；后续其他受邀者应按原runbook发放独立账号，不群发所有者密码，本轮没有修改邀请名单。

使用严格公共证书验证的Python及浏览器，不跟随API验收重定向以免凭据误发；本地证书检查绕过HTTP代理。Caddy默认不信任传入的X-Forwarded请求头，伪造头拒绝请求另测，不宣称已完成真实客户端IP审计。前端沿用同源相对/api/v1；本轮验证搜索/图表/手机布局，不新增Cookie/跨域/WebSocket配置。

## 验证与失败记录

启动前 scripts/verify_production.py 的11项源站TLS/认证/重定向/只读检查通过。原13容器（11running/2历史stopped）和原配置快照在data/acceptance/m6-business-trial-20261012/。

第一次门禁失败即关闭，未交付URL，原脚本没有保存逐项结果，不能确证是哪一项失败。检查发现行情接口需要start_date/end_date，已补齐，未改业务接口。第二次逐项证据显示带伪造代理头的未认证首页请求403，脚本误要求401，因此自动关闭；修正测试预期：普通未认证请求必须401，伪造头请求允许401/403，均不得返回业务数据。此修正不改变任何认证或服务配置。两次失败窗口state.json均process_stopped=true，失败记录保留。最终窗口、浏览器和外网结果见下方续记。

脚本Ruff检查/格式通过。直接.venv/bin/pytest曾因sys.path未包含仓库根目录在collection阶段失败；改用.venv/bin/python -m pytest deploy/tests -q，18passed/0.05s。未重跑会创建数据库的后端集成测试。

## 操作与关闭

从仓库根目录启动，仅在明确授权窗口使用（output必须是新目录，拒绝覆盖）：

```bash
python3 deploy/acceptance/business_tunnel.py --binary /tmp/stockinsight-quick-tunnel-1qisi_g3/cloudflared --output data/acceptance/m6-business-trial-20261012/trial-4 --duration 3600
```

本轮在私有终端读取既有邀请密码，不粘贴聊天或截图：

```bash
cd /home/crazychen/myprojects/StockInsight
cat secrets/production/preview_password
```

浏览器打开实际URL后输入preview及本地读取的密码。邀请凭据不要放到URL。保持Windows/Ubuntu/WSL、Docker和Tunnel运行；电脑休眠/关机/断网会中断试用。

提前关闭本轮入口：

```bash
cd /home/crazychen/myprojects/StockInsight
touch data/acceptance/m6-business-trial-20261012/trial-4/STOP
```

脚本仅终止自己的cloudflared子进程；不停止原容器。到期自动关闭，state.json写process_stopped=true，随后请求URL应不再返回业务内容（通常530）。保留官方临时二进制，无systemd服务或自动开机运行。本轮脚本不接受任意origin，避免误指开发或数据库。

## 验收边界与下一步

此为临时受邀只读试用，不代表稳定地址、长期可用、行情公开分发授权或M6-04完成。当前约100股样本99成功/1失败、混合维护51请求失败、真实异地备份和恢复/RPO/RTO、WSL电源恢复与重连仍按原M6证据保留。正式运行前需确定个人邀请/撤销、Access可选方案、固定域名与账号、代理IP信任审计、持续运行及外部告警和真实灾备；任何购买或Git远端操作仍需单独授权。

参考：[Cloudflare源站TLS/Host参数](https://developers.cloudflare.com/tunnel/reference/origin-parameters/)。


第三次窗口普通未认证请求前7项401，随后请求异常退出；当时未记录异常类型，不能确证原因，窗口自动关闭。第四次新增有限出站重试及异常类型记录，实际记录URLError；独立比较既有代理与直连的未认证/source-settings均401，说明单次异常不能判定入口不可用。保留全部失败记录，不将失败窗口改判通过。


### 最终交付状态：业务试用已开启

本轮第四窗口QUIC注册成功，公网地址 https://eyed-toll-chairs-resolutions.trycloudflare.com ，源站https://localhost:18443；证据trial-4/state.json。公网门禁23项通过：12条未认证路径401、伪造代理头请求拒绝、认证后页面/API/真实行情查询200、docs/openapi404、source-policy PUT403。保持源站CA/主机名校验与公共HTTPS校验，未关闭TLS验证。源站11项检查通过。

浏览器首次使用系统Node18时因Playwright要求Node20+未运行；改用已有Node22.23.1，无系统安装。严格公共证书验证的Playwright真实搜索贵州茅台、K线/均线、只读设置、失败任务可见、教程、桌面/390px手机布局通过，无页面脚本错误；截图及browser-probe.json在本轮Git忽略证据目录。已向用户提供手机蜂窝登录步骤，业务外网人工反馈待取得，不能以旧静态测试反馈替代。

限时窗口从13:23:45计时，预计北京时间14:23:45自动关闭。当前Tunnel按用户授权保持运行供试用，尚未到期，不把关闭结果预先标通过；提前关闭命令见上文STOP步骤。此窗口不承诺永久地址/稳定可用；重启会换URL。实际记录URLError有限重试恢复，稳定性风险保留，最终门禁全部通过并不抹去原失败窗口。

原13容器ID/启动时间/restart/镜像/端口/网络和部署及私有env哈希前后完全一致，生产DB仍Internal=true。仅业务GET验证与代理入口拒绝的PUT，没有数据库管理操作、采集扩容、Schema或数据迁移；服务既有正常日志与后台调度仍可自行写入。不改原M6_ACCEPTANCE/PRODUCTION_RUNBOOK或Caddy/Compose，不提交/推送/合并Git。


### 手机业务反馈（2026-10-12 13:28，Asia/Shanghai）

用户明确反馈“登录成功，搜索和 K 线正常”，完成本轮手机外网业务功能验证。此回复没有单独再次说明证书警告，严格公共证书正常仍引用本轮程序及浏览器实测，不扩写用户反馈。证据trial-4/external-feedback.json。当前窗口仍按原授权保留至14:23:45自动关闭，不提前停止，不自动续期；窗口清理和入口失效核验尚待到期，M6-04与原失败项不变。原服务/配置/数据库无新增操作，Git无提交/推送。
