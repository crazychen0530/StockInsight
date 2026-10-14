# 在现有WSL主机启动StockInsight

适用：当前已有stockinsight-m6容器、镜像、私有配置及数据的Ubuntu/WSL2主机。Git仓库不含数据库、密码或私有.env；新电脑需要按[M6生产运行手册](M6_PRODUCTION_RUNBOOK.md)准备环境，不能仅clone后执行脚本得到现有数据。

## WSL与Docker启动

2026-10-12只读核验：本机/etc/wsl.conf启用systemd=true，Docker服务enabled且active，Docker29.1.3。因此按当前配置打开此Ubuntu WSL会启动Docker，无需每次手动启动Docker Desktop；本机使用WSL内的Docker Engine。未执行WSL关机/冷启动实测。

等Docker就绪后，日常进入项目目录只需执行./stockinsight.sh public。它包含启动现有服务及健康检查，无需先执行start。若提示Docker不可用，先稍候并执行docker ps；确实未运行时由用户执行sudo systemctl start docker，再重试。此脚本不自动sudo。

## 每次使用

打开WSL，确认Docker已经启动；脚本使用已有Python3、Docker及/usr/bin/curl，不需要激活Python虚拟环境或前端Node，不自动sudo或安装系统软件：

```bash
cd /home/crazychen/myprojects/StockInsight
./stockinsight.sh start
./stockinsight.sh public
```

public也会先执行start，所以只想公网访问时可以直接执行第二条。等待门禁通过后，终端打印临时HTTPS地址及北京时间到期时间；访问无需登录，默认8小时（28800秒）。首次使用复用已核验官方工具或从官方GitHub下载固定版本并校验SHA256，保存在Git忽略的data/tools；不再依赖/tmp。下载失败会停止，不关闭TLS校验。

授权状态：用户已明确允许股票目录、日线K线、均线及任务/来源状态通过运行时生成的trycloudflare.com地址匿名公开8小时；追加确认后自动审批通过，实际公网及手机验证成功。前次拒绝和失败窗口作为历史证据保留。

保留此终端和WSL、Docker、电脑网络；关机/休眠/关闭终端可能中断服务。临时网址每次变化，8小时是本机脚本时间，不是可用性保证。可以发给其他人，匿名访问没有个人撤销能力；若不希望任何链接持有者访问，应停止窗口并恢复受邀方式，不将网址保密当作认证。

## 查看状态和停止

在另一个WSL终端：

```bash
cd /home/crazychen/myprojects/StockInsight
./stockinsight.sh status
./stockinsight.sh public-stop
```

public-stop请求当前根目录脚本窗口关闭；也可在启动终端Ctrl+C。到期/STOP/中断后，启动脚本清理自己的cloudflared及自己的临时代理容器，不停止原开发/生产容器。运行状态和脱敏证据保存在data/runtime及data/acceptance（均Git忽略）。如果窗口仍在准备阶段，使用原终端Ctrl+C。脚本不提供清库/全局停止命令。

临时修改时长，例如4小时：

```bash
./stockinsight.sh public --seconds 14400
```

支持60..86400秒，默认28800；修改新启动窗口参数不会延长已运行窗口。重复开启会被锁阻止。由于是前台程序，不支持关闭终端后自动后台运行，也没有安装开机自启服务。

## 本地入口与保护范围

- 原生产演练入口仍为https://localhost:18443，保留preview邀请认证与原内部CA。
- 公网匿名模式使用独立Caddy容器，仅127.0.0.1:18843，只有ingress私网，无数据库网络、无生产密码/私钥挂载。配置[匿名预览代理](../deploy/Caddyfile.public-preview)，原Caddyfile不动。
- Tunnel源站HTTPS验证独立公开CA及localhost主机名，绝不使用noTLSVerify。
- 只允许GET/HEAD查询；POST/PUT/PATCH/DELETE/OPTIONS/TRACE拒绝，docs/redoc/openapi、隐藏文件和未列出的API拒绝。前端来源设置只读。
- start只恢复现有M6的db/api/proxy/scheduler/backup/monitor，不自动建新数据库、migrate、构建或重建容器，不启动/修改开发环境。已有同机备份测试接收器不等于真实异地备份。
- 原开发环境若已运行仍在http://127.0.0.1:5173；本脚本不把开发管理接口开放至公网。

只做本地验证、不建立Tunnel：

```bash
./stockinsight.sh public --local-only --seconds 60
```

独立代理创建后19项严格源站TLS/匿名查询/调试隐藏路径/禁写检查完成即清理。用于确认配置，不能代替公网及手机验收。

## 故障处理

### public 在隧道注册后退出

后续同日用户复测发现首页200而/stocks返回530，退出阶段为public_gates。现在每项公网GET检查都有约60秒的限时传输/边缘错误等待（单次探测收尾可能再耗时25秒），包括必须最终404的隐藏路径；错误地返回200不会通过隐藏路径检查，写方法门禁仍严格要求拒绝。state.read_gate_probes保留各项尝试，失败提示显示具体路径与HTTP状态。短时门禁通过不能证明Quick Tunnel全程稳定；持续530仍清理本轮入口。

2026-10-14 实际失败证据中，原HTTPS的11项检查通过、Tunnel已registered，但公网首页探测 `last_curl_exit=6`（域名解析失败）；稍后同域名能解析且旧窗口返回530。该证据指向启动时临时DNS不可用，不能据此确定是DNS发布延迟还是本机解析网络问题。

脚本现在在隧道注册后增加约120秒的限时DNS/HTTPS就绪等待，仅重试解析、连接、超时及502/503/504/530等启动错误；TLS校验失败或非预期状态仍终止。就绪后仍须通过全部19项公网只读门禁才打印可用地址。DNS等待预算不包含单次最多25秒探测的收尾，默认8小时窗口仍从Tunnel进程启动计时。

若仍失败，终端会提示DNS/HTTPS错误类别并打印本次脱敏证据目录。检查其中的 `state.json`（stage、last_curl_exit、startup_last_result、failure_type）与 `gates.json`；仅registered不代表公网可用。保持终端与网络正常，稍后重试原命令 `./stockinsight.sh public`。不通过修改系统DNS或关闭TLS校验来掩盖错误。

本次 `./stockinsight.sh public --seconds 60` 实际通过原HTTPS11项与公网19项门禁，随后退出并清理自己的进程/临时容器；这不是8小时稳定性或用户手机浏览器验收。

Docker不可用：在原环境启动Docker/WSL后重试；需要sudo时由用户自行操作。容器缺失/拓扑改变：脚本拒绝自动重建，请按原运行手册恢复。18843端口被占用：先看status及是否有旧窗口，不停止未知进程。官方工具下载/隧道失败：检查网络及代理，保留脱敏证据；不关闭证书校验或映射数据库绕过问题。

## 临时匿名代理热加载

仅修改独立的deploy/Caddyfile.public-preview后可执行：

```bash
./stockinsight.sh public-reload
```

脚本核验本轮owner标签和路径，先验证新配置，原子替换目录挂载中的文件，再给自己的临时Caddy发送USR1。未开启管理HTTP接口；不重建容器，不更新原带认证生产代理。配置失败保留旧配置。命令提示“已请求”不代表生效验收，应检查响应及日志；本轮热加载演练结果见[修复记录](M6_REMEDIATION_20261012.md)。

## 本机已应用的停牌修复

2026-10-12经针对性授权，仅scheduler/monitor更新为修复镜像，使用data/runtime/halt-scheduler.json及halt-candidate.env的独立配置，原私有配置不覆盖。日常start/public只启动现有容器，会保留修复版本；不要手动清理这两个配置文件。若使用Compose维护，需按[修复部署记录](M6_REMEDIATION_20261012.md)带已有transport告警CA与halt overlay，不要直接运行全量release退回旧镜像。停牌公告登记只到10月13日，届满须复核。
