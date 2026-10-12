# M6 生产运行手册

2026-10-12。用户要求运行整个 M6，随后确认尚无服务器、域名、异地备份目标。已实现生产部署与本地演练；公网验收仍待资源和行情展示授权。验收事实见 [M6 验收](M6_ACCEPTANCE.md)，初始成本模型见 [容量评估](M6_CAPACITY_ASSESSMENT.md)。

## 部署组成

独立 `compose.production.yaml`，不与开发 Compose 合并。Caddy 提供静态前端、同源 API、HTTPS 和逐人 Basic Auth；API 不启用 reload，调度保持独立单进程。只发布代理 80/443，PostgreSQL/API 均无宿主端口。应用非 root、只读根目录、丢弃 capabilities，日志限制 10MiB×3；Caddy 脱敏请求日志同样轮转，不保存 URI、头和客户端 IP。

数据库 bootstrap 创建 `si_owner`（显式 migration）、`si_api`（SELECT）、`si_worker`（SELECT/INSERT/UPDATE，无 DELETE）、`si_backup`（SELECT）。应用不使用数据库管理员。SQL 仅在新卷首次启动时执行；已有数据库角色升级必须另行设计，不能以重启替代。无业务 Schema/migration 改动。

`secrets/production` 为 0700；被选中挂载的 secret 文件 0444，使 Compose bind secret 可供非 root 容器读取，宿主其他用户无法穿过父目录。口令文件及真实 env 不进 Git。Docker 管理员属于受信任运维边界。备份密钥必须单独离线保管；丢失后无法恢复。

## 初始化和构建

要求 Linux、Docker Engine/Compose/Buildx、Python 3.12。先核对已有项目和卷，不运行 `down -v`、清库或全局 prune。以下命令在仓库根目录运行，镜像标签用实际提交 SHA，保留上一版。

```bash
docker build -f deploy/Dockerfile.backend -t stockinsight-production-app:COMMIT_SHA .
docker build -f deploy/Dockerfile.proxy -t stockinsight-production-proxy:COMMIT_SHA .
docker build -f deploy/Dockerfile.operations -t stockinsight-production-ops:COMMIT_SHA .
python3 scripts/init_production.py --image-tag COMMIT_SHA
```

初始化不覆盖已有凭据；默认仅 loopback 18080/18443、localhost 内部 CA、4 股名单，不会自动采集。生产 proxy 镜像构建注入 `VITE_READ_ONLY_DEPLOYMENT=true`，页面不显示管理口令/设置表单，API 与代理同时拒绝写入。镜像只安装锁定运行依赖；ops 另含 pg_dump/GPG/OpenSSH。需要构建代理时用 Dockerfile 的 BuildKit `build_proxy` secret，不能用 build args 或关闭 TLS 验证。

部署人员通过私有终端读取 `secrets/production/preview_password`；不把值写在命令参数、报告或 Git 中。首次发放前用 `manage_invites.py` 创建实名对应的独立用户名，安全通道分别交付密码。示例：

```bash
python3 scripts/manage_invites.py add reader01
docker compose --env-file .env.production -f compose.production.yaml up -d --no-deps --force-recreate proxy
python3 scripts/manage_invites.py revoke reader01
docker compose --env-file .env.production -f compose.production.yaml up -d --no-deps --force-recreate proxy
```

密码在私有目录独立文件中，Basic Auth 不提供应用角色体系；首期所有受邀用户只读。浏览器可能缓存凭据，撤销后后续请求应返回 401。

## 本地演练

```bash
python3 scripts/release_production.py --rehearsal
docker compose --env-file .env.production -f compose.production.yaml cp proxy:/data/caddy/pki/authorities/local/root.crt secrets/production/local-ca.crt
python3 scripts/verify_production.py
```

入口 `https://localhost:18443`，HTTP 18080 重定向。浏览器需显式信任演练 CA；Python 检查严格验证 CA/主机名，无 `-k`。空的新库需用原有 CLI 初始化真实目录/行情后再检查，不能写入 fixture。调度配置位于私有 `config/scheduler.json`；此次 `config/universe/preview-100.json` 是容量样本，原 4 股加目录中升序 96 股，非投资推荐或最终业务名单。名单/起点变更需运维显式复制并重建 scheduler/monitor，不自动扩采开发库。

单次采集使用既有 CLI 与相同名单，或直接启用独立 daemon：

```bash
python3 scripts/release_production.py --rehearsal --automation --operations
```

`--operations` 仅在已配置 SSH 目标时启用，后台每日加密备份；未配置时显式失败并重试。`--automation` 开启真实采集，盘后 17:30、catch-up、防重沿用现有 scheduler。当前来源私有配置为腾讯，不改变原开发环境策略。

本次 SSH/HTTPS 告警接收器由 `deploy/acceptance/transport.compose.yaml` 提供，仅无发布端口的同机测试服务。需要专用主机密钥/客户端密钥/known_hosts 与带 SAN 的测试 HTTPS 证书，放在 Git 忽略的 `TRANSPORT_KEYS_DIR`；不得用于公网。真实备份应指向不同故障域。测试 overlay 的 `SSL_CERT_FILE` 只信任此测试告警 CA，常规 release 不自动加载测试 overlay。

## 公网部署条件与发布

私有 `.env.production` 配置真实 DOMAIN、ACME 联系邮箱 `TLS_ISSUER`、`TLS_HOST`、80/443、`PROXY_BIND=0.0.0.0`，且 DNS 指向目标主机。防火墙只开放所需 HTTP/HTTPS 和受限 SSH。确认行情用途后显式 `DATA_USE_CONFIRMED=true`；配置独立 SSH 备份账户/目标绝对目录、已通过其他可信方式验证的 known_hosts、专用备份私钥和真实 HTTPS 告警 URL。不要将 `ssh-keyscan` 结果未经核验直接当可信。

```bash
python3 scripts/release_production.py --preflight-only
python3 scripts/release_production.py --automation
```

脚本核验公网条件、镜像存在和 Compose；启动数据库、初始化新卷权限、记录上一版镜像 ID/当前 schema、备份成功后显式 migration，最后启动 API/proxy/monitor/每日 backup（可选 scheduler），检查核心数据库查询。`data/releases/*.json` 为 0600 发布记录：失败保留 prepared 记录，完整通过后标 completed。配置/tag必须保持不变直至验收，真实交付使用提交 SHA 或 digest。

目标主机必须重新完成可信 HTTPS、邀请认证/撤销、页面搜索/K线/均线/失败状态、100 股采集、15 分钟10用户、日志/监控、真实异地恢复与回滚。当前本机 CPU 亲和性测试不能代替目标 VPS 的4GiB内存/公网/上游验收。

## 备份、恢复与回滚

```bash
docker compose --env-file .env.production -f compose.production.yaml run --rm backup python3 /opt/operations.py backup
```

pg_dump custom 流直接经 GPG AES-256 加密，明文不落盘；本机原子归档、严格 SSH 主机校验、远端 SHA-256 一致后转正式文件并写成功回执。每天一次，失败一小时后重试，监控超过26小时告警。只在确认传输成功后删除本机受管归档，保留最近7个备份日期和4个ISO周代表；远端默认追加，独立备份管理员另配保留/容量/不可变策略，应用账户不删远端档案。`--local-only` 仅演练，不算异地成功。

恢复先由受控数据库管理员创建独立空数据库，例如 `stockinsight_dr_restore`、owner `si_owner`，不发布其端口。修改私有 env 的 `RESTORE_DATABASE` 后执行：

```bash
docker compose --env-file .env.production -f compose.production.yaml run --rm restore python3 /opt/operations.py restore --archive /backups/ARCHIVE.dump.gpg
```

脚本拒绝非 `_restore` 数据库及已有 public 表，单事务 `pg_restore --no-owner --no-acl`。核对备份哈希、revision、所有表行数/内容哈希、约束/索引及只读 API 后，另行制定受控切换；不自动覆盖生产库。本次耗时仅本地数据恢复，不含新主机、密钥取回、下载、DNS等完整灾备时间，RPO24h/RTO2h仍是目标。

```bash
python3 scripts/rollback_production.py data/releases/RECEIPT.json
```

回滚先核对当前 schema 与发布前一致，再以记录的不可变镜像 ID 恢复 API/proxy/monitor（原发布启用的 scheduler/backup 同步恢复），写新的0600 rollback env，不覆盖当前 env。schema变化时拒绝镜像回退，按独立恢复方案处理；首次安装没有上一版时也拒绝。不得默认执行数据库 downgrade 或删除卷。

## 监控与值班

monitor 每10分钟核验业务查询、名单中每股实际水位、日历覆盖/到期、数据库卷磁盘、宿主内存、代理近5分钟 p95/5xx、已校验远端备份时间及公网证书有效期。阈值：磁盘70%、内存80%、p95 500ms、5xx 1%、证书剩14天、日历剩30天。行情延迟在交易日18:30后要求当天，之前要求上一交易日。

状态写入 ops_state 的 monitor.json，告警 POST HTTPS，失败安全记录，不记录 URL/口令。备份失败即时尝试告警；主机/网络整体故障无法依靠同机 monitor 自报，公网交付时仍需外部存活监测和值班负责人。不得把“告警 URL 已填”写成“有人收到”，应让接收方确认。
