# StockInsight 部署规划

> 2026-10-12最新：暂不购买VPS；已明确授权8小时匿名只读Quick Tunnel，程序/手机验证通过。用户暂不合并或推送，继续处理剩余问题，见[修复记录](M6_REMEDIATION_20261012.md)。原M6验收证据及部署配置保留，长期生产验收尚未完成。

> 状态：M6生产部署实现与本地演练完成，公网资源尚无
>
> 当前阶段：M0–M5完成；M6-01～03完成，M6-04公网部署TODO。最新实施以[生产运行手册](M6_PRODUCTION_RUNBOOK.md)和[验收报告](M6_ACCEPTANCE.md)为准；下文评估/未实施描述保留历史时点。无采购；已完成授权限时公网试用，未完成长期生产部署。

## M6-01 当前评估（2026-10-12）

用户确认首期2–10名受邀用户、约100只股票、先评估成本。[容量评估报告](M6_CAPACITY_ASSESSMENT.md)记录本轮只读基线、并发短样本、存储增长、串行采集与备用延迟风险、候选规格、费用/地域/域名及目标环境验收门禁。首期候选为2 vCPU/4 GiB/80 GiB，尚未在限定资源/100股/生产镜像上验收；当前库仍仅4股732条，不自动扩大采集名单。

[ADR-022](DECISIONS.md#adr-022m6-受邀预览部署与容量方案)为Proposed，供后续生产配置实施确认。费用是官方页面参照，预算、地域、域名、股票名单/历史起点、数据用途许可和恢复目标待决定；没有采购、域名操作、生产发布或远程推送。本文件后续未实施的生产章节仍为规划，以该报告为本次评估结果。

## 1. 本地开发部署方式

M1 支持两种本地方式，具体命令见 [README.md](../README.md#本地-docker-compose)：

1. 混合开发：Docker Compose 运行 PostgreSQL，后端和前端使用宿主机开发服务器，以便调试和热更新。
2. 全容器开发：使用根目录 `compose.yaml` 运行 `db`、`api`、`web`。M5 可显式启用 automation profile 加入独立 scheduler；默认三服务不采集。

本地配置从 `.env.example` 派生到不进入 Git 的 `.env`。数据库 migration 必须由明确的 Alembic 命令执行，不允许应用启动时隐式修改 Schema。测试数据库与开发数据库隔离。

M1-01 已验收：Python 3.12.3 在仓库内 `.venv` 隔离；Node.js 22.23.1 通过 NVM 并行安装且由 `.nvmrc` 固定，系统 Node.js 18.19.1 未替换；Docker Engine 29.1.3、Docker Compose 2.40.3 和 PostgreSQL 客户端 16.15 已安装。当时的 systemd、Docker service、用户组权限和 `./scripts/check_environment.sh` 全部通过。M1-02 会话再次执行脚本时，Docker daemon 报告不可达或当前进程无权限；开始 M1-05 前必须重新验证并定位，不能沿用旧结果。

M1-05 复核确认 daemon 在提升权限后可达；官方 Registry 经现有 shell 代理可访问，但 daemon 未配置代理，直接 pull 超时。本次从 Ubuntu 包仅解压 skopeo 及依赖到 `/tmp`，经既有代理下载 Docker Hub 官方镜像并导入 daemon；没有系统安装或修改 daemon 配置。镜像导入后构建和三服务运行验收通过，详细结果见 `SESSION_HANDOFF.md`。

### 1.1 本地实现边界

- PostgreSQL 使用官方 `postgres:16-bookworm`；后端与前端分别基于官方 Python 3.12 和 Node.js 22 Debian 镜像。
- 默认项目名 `stockinsight-local`，卷名由 Compose 项目隔离，不声明 external 卷或固定容器名。
- PostgreSQL/API/Vite 端口全部只绑定 `127.0.0.1`；数据库服务名固定为 `db`，容器间使用 5432。
- `api` 等待数据库健康，`web` 等待 API 进程健康；健康检查不会执行 migration。
- `scripts/init_local_env.py` 只在 `.env` 不存在时创建随机本地密码和 0600 文件，现有文件不会覆盖。
- Alembic 必须由运维显式执行 `docker compose exec -T api alembic upgrade head`；账户密码经环境变量传入，不写进 URL。
- API 与 web 使用非 root 应用用户；开发镜像包含测试工具，源码只读挂载支持热更新。
- Vite `/api` 代理提供页面统一客户端到本地只读查询 API 的入口。
- `stop`、`start`、`down` 都保留数据卷；没有自动清库逻辑。不得未经授权执行 `down -v`。

实现参考 Docker 官方文档：[依赖启动与健康检查](https://docs.docker.com/compose/how-tos/startup-order/)、[Compose 网络与服务发现](https://docs.docker.com/compose/how-tos/networking/)。

## 2. Docker Compose 服务说明

M1-05 已定义前三个服务，其余服务只作 M2-M6 规划：

| 服务 | 职责 | 暴露策略 |
| --- | --- | --- |
| `db` | PostgreSQL 数据库与健康检查 | 本地可绑定 `127.0.0.1`；生产不映射公网 5432 |
| `api` | FastAPI 查询 API | 本地开发端口；生产仅由反向代理访问 |
| `web` | Vue 构建或开发服务 | 本地开发端口；生产静态文件由反向代理提供 |
| `worker` | 手工补采或批处理执行入口 | 不暴露公网端口 |
| `scheduler` | 交易日盘后触发增量任务 | 单实例，不嵌入 API 多 Worker |
| `proxy` | Nginx 或 Caddy、TLS 与路由 | 生产仅公开 80/443 |

开发和生产 Compose 可使用基础文件加显式环境覆盖，但生产密钥、证书和持久化路径不能提交 Git。服务名及拆分在 M1 实现时可作非重大调整；改变独立 Worker 或数据库网络边界属于架构变更。

## 3. 生产环境目标架构

```text
Internet
   |
HTTPS 443
   |
Nginx/Caddy
   |-- Vue 静态资源
   `-- /api/v1 -> FastAPI
                      |
Worker/Scheduler -----+----> PostgreSQL（私有容器网络）
         |
         `----> AKShare/上游数据源（受控出站访问）
```

生产环境以 Linux VPS 上的单机 Docker Compose 为首选。API、Worker 和 Scheduler 使用相同版本镜像但不同启动命令。PostgreSQL 只允许私有网络访问；备份写入权限隔离的位置，并按策略复制到独立存储。

## 4. Linux 云服务器建议配置

当前没有真实负载数据，以下只作为 M6 初始评估区间，不构成购买建议：

- 起步候选：2 vCPU、4 GB RAM、60-100 GB SSD。
- 操作系统：受支持的 Ubuntu LTS。
- 存储：优先选择可扩容 SSD，并为数据库、备份和日志保留容量告警。
- 区域：根据主要访问者、数据源网络可达性、法规和备份位置选择。

M5 后必须用实际股票数量、历史区间、数据库体积、采集耗时、API 延迟和备份耗时重新估算。不能仅凭上述候选规格采购。

## 5. 何时需要购买云服务器

必须同时满足：

1. v0.1.0 本地 MVP（M1-M5）验收完成。
2. 后端、前端、migration、采集、调度和核心端到端测试通过。
3. Docker Compose 已在全新 Linux 环境验证。
4. 数据采集稳定，并已确认数据源授权和公开展示方式。
5. 身份/访问控制、HTTPS、安全配置和依赖风险已复核。
6. PostgreSQL 备份与独立恢复演练通过。
7. 项目所有者明确决定需要公网访问并批准预算和部署。

当前真实本地运行与 M5 验收不等于公网授权，仍不满足购买条件。M1 阶段记录：M1-06 保持三服务和持久卷不变，显式注入环境/日志级别/时区，禁用原始 Uvicorn access log，使用带服务端关联 ID 的脱敏 JSON 日志。`APP_ENV=production` 不等于完成生产访问控制或安全验收。

## 6. 域名与 HTTPS 配置方案

- 项目所有者购买或指定域名，并控制 DNS 账户；Codex 不自行采购。
- DNS 的 A/AAAA 记录指向获批服务器；变更前记录旧值和回滚方法。
- 优先使用 Caddy 自动签发/续期 Let's Encrypt 证书，或使用 Nginx 配合 Certbot；最终选择在 M6 记录为技术决策。
- HTTP 80 仅用于 ACME 验证和重定向至 HTTPS；应用流量使用 443。
- 启用现代 TLS、安全响应头和合理的请求体/速率限制；证书私钥不进入 Git。
- 部署前验证续期流程，而不只验证首次签发。

## 7. 数据库备份和恢复方案

计划采用分层策略，最终频率根据 M5 数据量与恢复目标确认：

- 使用 `pg_dump` 生成逻辑备份，文件名包含 UTC 时间、数据库版本和应用版本。
- 备份加密后复制到与 VPS 故障域隔离的受控存储，执行保留和过期策略。
- 数据卷快照只能作为补充，不能替代可移植的逻辑备份和恢复验证。
- 恢复必须写入独立 PostgreSQL 实例，运行 migration 状态检查，并核对表、约束、关键行数和核心查询。
- 记录 RPO、RTO、备份耗时、文件大小、校验和与恢复结果；未演练的备份不能视为可恢复。
- 数据库凭据和备份加密密钥分开管理，不写入日志或仓库。

## 8. 生产环境安全要求

- 仅开放必要的 SSH、80 和 443；PostgreSQL 5432 不暴露公网。
- SSH 使用密钥和最小授权，关闭不需要的密码登录和 root 远程登录，并配置防火墙。
- 应用、migration、只读查询和备份账户按最小权限拆分；定期轮换凭据。
- 密钥通过服务器 Secret/环境管理注入；禁止写入镜像、Compose 仓库文件或前端产物。
- 固定依赖与镜像版本，扫描已知漏洞；基础镜像和系统安全更新有维护窗口。
- 日志结构化、脱敏并轮转；设置磁盘、数据库、API、采集失败和证书到期告警。
- 管理采集入口不得匿名暴露公网；生产变更要有审计记录和回滚点。
- 定期验证备份恢复，并限制备份文件访问权限。

## 9. GitHub 到服务器的发布流程

目标流程如下，M6 实施前仍需项目所有者确认具体 CI/CD 权限：

1. 功能分支通过代码审查和测试后合并到稳定 `main`。
2. 里程碑验收后创建经授权的版本标签；CI 从指定提交构建不可变镜像。
3. CI 执行后端测试、前端类型/组件测试、migration 测试、依赖与密钥扫描。
4. 镜像推送到获批的私有 Registry，使用提交 SHA/版本标签，不依赖可变的 `latest`。
5. 先备份数据库并记录当前镜像和 migration revision。
6. 服务器只拉取已批准镜像，先运行显式 migration，再按顺序更新 API、Worker、Scheduler 和静态前端。
7. 执行健康检查、核心只读查询和页面冒烟测试；失败时停止推广并回滚。

未经用户授权不得创建远程仓库、配置生产 Secret、push、发布 Release 或触发生产部署。生产服务器不应通过 `git pull` 加临时改动的方式发布。

## 10. 生产环境回滚方案

- 发布前记录上一版本镜像摘要、Compose 配置、环境配置版本、数据库 revision 和备份标识。
- 应用级失败时，将服务切回上一不可变镜像并重新执行健康检查。
- migration 必须在开发阶段评估向后兼容性；优先采用先扩展、后迁移、再收缩的方式，使旧应用可在过渡期运行。
- 数据库降级只有在 Alembic downgrade 已测试且不会丢失数据时执行；否则从发布前备份恢复到独立实例，经核验后切换。
- 前端静态资源按版本保留，可切回上一构建。
- 回滚后保留脱敏日志、时间线和影响范围，建立修复任务；不得用强制推送改写 Git 历史掩盖生产问题。

## 11. 当前部署状态

- 未购买云服务器，未配置域名、TLS、生产 Compose、公开 Registry 或 CI/CD 发布。
- 本地开发库 revision `0001_initial_schema`、股票 5,223、日线/指标各 732；默认 4 只股票，保留原卷。
- db/API/web healthy，automation scheduler 常驻，全部宿主端口仅 loopback；真实采集与重启防重已验收。
- 加密备份已在独立 PostgreSQL 实例恢复并核对完整内容、约束、索引与 API；没有删除原库/卷。
- 全新 Ubuntu 独立 VM/Docker 的具体步骤和结果见 [M5 验收](M5_ACCEPTANCE.md)，不以原开发环境替代。
- M4 main 已同步私有 GitHub，M5 在功能分支完成后另按授权同步；本地开发镜像不直接宣称可公网生产部署。

以下 M2/M3/M4 小节是当时的阶段记录，当前状态以本节与 M5 专题为准。

## M2-05 本地采集进程

已新增宿主机 `.venv/bin/python -m app.jobs.cli`，使用现有环境配置与数据库，详见[操作说明](COLLECTION_CLI.md)。CLI 独立于 API 生命周期，无自动 migration、不嵌入 API 或新增常驻服务。现有 Compose 三服务和原卷保留，当前 API 开发镜像未加入可选 market-data extra，不声称容器 CLI 已验收；本轮使用已安装 extra 的宿主机 venv。尚无调度、公网入口或生产部署变化。

## M3-01 查询进程

现有 API 新增[三个股票只读入口](STOCK_QUERY_API.md)，按需初始化查询连接并在应用关闭时 dispose；健康检查保持独立。复用现有配置、开发库和 Compose 三服务，无新端口、migration、数据填充或公网部署。数据库 read-only 事务不替代后续生产账号最小权限配置。

## M3 前端本地入口

本地 web 已使用 Axios `/api/v1` 查询并通过既有 `/api` 代理转发；概览、搜索/详情、K 线和成交量见[前端专题](FRONTEND_MARKET.md)。新增前端依赖后需 `docker compose build web` 再 `docker compose up --detach --no-deps --no-build --wait --wait-timeout 120 web`，只更新 web，保留 db/API/卷。本轮已完成此操作，仍仅本机 5173 可访问。生产静态托管必须配置 Vue history 路由回退和同源 `/api` 反向代理，留待 M5/M6；Vite Preview 不替代生产部署。

## M4 本地分析与调度入口

M4 已完成均线、指标/任务状态只读 API、详情均线与 `/data-status`、独立宿主机调度 CLI。调度沿用独立进程设计；默认 Compose 仍仅 db/api/web，原卷保留，不自动启动网络采集。无需新依赖、数据库迁移或服务器。参见[均线](MOVING_AVERAGES.md)、[调度](SCHEDULER.md)和[运维操作](OPERATIONS.md)。生产进程监督、账号权限、真实日历/上游验收、全新 Linux、备份恢复仍属于 M5/M6，不能用本地测试替代。

## M5 本地自动更新与验收入口

默认三服务不采集；用户显式启用 `automation` profile 后，独立 scheduler 按已核验 2026 日历与 4 只股票名单执行真实采集，带启动补齐和持久防重。所有端口仍仅 loopback，数据库卷保留。构建使用 `backend/constraints.txt` 锁定已审计 Python 3.12 依赖，前端使用 `package-lock.json`。Dockerfile 可选 BuildKit `build_proxy` secret，仅在依赖安装 RUN 中读取，禁止将带凭据代理作为 build args。

详细命令见 [README](../README.md#真实采集与自动更新)，真实数据、全新 Linux、依赖审计及加密备份恢复的证据统一见 [M5 验收报告](M5_ACCEPTANCE.md)。本地开发 Compose 包含 dev 依赖及 Vite，不直接宣称满足公网生产部署；M6 的 HTTPS、认证、最小权限生产账户、告警、日志轮转与异地备份另行实施。


## 本地网页管理增补（2026-10-12）

当前development API新增来源策略读写，不再是全部只读接口；仅修改有限配置，不触发采集。LOCAL_ADMIN_TOKEN经私有.env注入API，scheduler不接收该口令。共享data/source-settings目录API可写、scheduler只读，需保证非root应用UID10001可访问；初始化命令见README。production明确拒绝此写接口，不能将本地管理机制直接当作M6公网认证。Vite代理保留本机Host，来源管理额外验证固定本机Origin和口令，阻止跨站/DNS重绑定写入。无数据库Schema、端口或公网部署变化。


## 限时业务公网试用补记（2026-10-12）

用户明确“授权业务公网试用”，ADR-024接受仅此范围；现有主机一小时Quick Tunnel，严格校验源站HTTPS，沿用原Caddy邀请认证/只读入口。独立启动脚本deploy/acceptance/business_tunnel.py、严格TLS浏览器frontend/scripts/browser-tunnel-trial.mjs、报告docs/M6_BUSINESS_TRIAL_20261012.md。不修改原生产配置或既有容器/数据库，不注册账号/购买/安装系统软件，不commit/merge/push。原M6失败项保持。具体结果及当前URL以后续最终补记和证据state.json为准；初始三个窗口关闭且失败证据保留，第四窗口有限重试后继续门禁。


## 当前交付评审与8小时匿名启动（2026-10-12，替代前轮下一步）

用户要求检查未修复问题，若没有则合并main并推送；追加明确要求公网8小时且无需登录。当前仍有100股99/100未就绪、混合维护51失败、真实异地备份/长期运行未验收，因此不声称无问题，不根据附条件指令自动合并/推送。新增docs/V0_1_DELIVERY_REVIEW.md具体列出限制；docs/LOCAL_SERVER.md和根目录stockinsight.sh提供当前现有WSL主机启动/public/status/public-stop，默认28800秒。匿名入口采用独立临时Caddy/公开CA，只连接ingress网络、不挂生产密钥，源站TLS严格验证、写方法403、隐藏/调试/未知API404，原localhost18443认证保留。

匿名公网启动经自动审批被拒绝，理由是需具体确认将业务行情/任务数据发送至运行时生成的公共目的地；没有绕过。仅执行--local-only：19项查询/禁写/路由/严格源站CA检查通过并清理本轮容器，无匿名公网URL。初始本地镜像能力与tmpfs CA复制适配失败已修正，保留NET_BIND_SERVICE及读取公开CA、不安装信任，精确owner标签清理，失败资源已清理。cloudflared复制到data/tools固定官方digest，不依赖/tmp，不系统安装。

本轮完整回归399后端/39前端/18运维均通过，Node22类型/构建通过（604KB详情chunk提示保留），新脚本Ruff/bash语法通过。全新6个隔离测试库保留，原业务库不变。实际远程main通过ls-remote核验为2cf6ff7a3024a4f90fd52f88d047423121f4b8c2；本地当前feature/m6-production-deployment HEAD4496600，未提交/合并/push，本轮工作区继续保留。不购买资源。前一带认证窗口已到期，state process_stopped=true，最终失效核验补记为准。

下一步等待两个明确决定：（1）是否接受docs/V0_1_DELIVERY_REVIEW.md列出的已知限制，以功能首版合并main并push origin；（2）是否允许具体行情目录、日线K线、均线、任务/来源状态通过随机trycloudflare.com地址匿名公开8小时。拿到决定后先核对本轮最新文件/审批范围，不自动把M6-04/旧失败项标DONE。未得到匿名批准时可继续本地start及local-only，不自动执行public。

## 当前剩余问题处理

[修复记录](M6_REMEDIATION_20261012.md)区分代码候选与运行部署：停牌修复的新app/ops镜像已隔离验证，并在用户针对性授权后仅更新scheduler/monitor应用overlay。当前匿名窗口23:37:08到期，既有本地HTTPS/认证、数据库私网及数据不变。真实异地目标和WSL恢复窗口缺失，M6-04不改判。

停牌修复已获用户针对性授权，实际仅更新scheduler/monitor；带原transport告警CA overlay和独立halt配置，补采158条真实历史后100股有历史。原API/代理/DB及配置不变；stockinsight.sh start保留现有镜像。详细运行回执、快照缺证据说明及维护失败见修复记录。

## 首版使用决定

用户2026-10-12接受已知限制并授权合并/推送main，其他问题待实际使用反馈。只交付现有主机首版，不将M6-04改为通过。已只读核验/etc/wsl.conf的systemd=true与Docker enabled/active；日常命令见LOCAL_SERVER.md。未执行WSL关机/冷启动实测，不安装新的系统服务。

## 学习页前端单服务更新（2026-10-13）

用户明确授权更新前端、验证 `/learn` 并合并推送。本次只替换 `stockinsight-m6-proxy-1`，原CA/认证/端口/卷保留；API、DB、scheduler、monitor、backup的ID与StartedAt前后一致。无运行中匿名代理，不自动续期开窗；下次用户主动public会使用新版生产代理镜像。

实际采用Node22：前端 `npm test`（44 passed）、`npm run typecheck`、`VITE_READ_ONLY_DEPLOYMENT=true npm run build-only`。构建上下文仅frontend/dist，以 `deploy/Dockerfile.frontend-update` 叠加已检查的本地原镜像 `stockinsight-production-proxy:m6-validated`，生成 `stockinsight-production-proxy:learn-20261013`（ID前缀1d0f94adc483）。本机无Buildx，使用现有legacy builder，无拉取/安装系统依赖；后续应恢复标准BuildKit。保留旧哈希资源兼容已打开页面，不无限累积历史资产，基础镜像升级仍走完整构建。

仅运行：

```bash
PROXY_IMAGE=stockinsight-production-proxy:learn-20261013 docker compose --env-file .env.production -f compose.production.yaml -p stockinsight-m6 up -d --no-deps --no-build --pull never proxy
python3 scripts/verify_production.py
```

首次启动即刻探测出现ConnectionResetError，随后11项全部通过；不宣称零停机。实际生产浏览器 `/learn` 与真实图表通过，TLS信任方式详见学习专题。已忽略的 `.env.production` 仅PROXY_IMAGE改为新标签。

回滚：把上面命令的PROXY_IMAGE恢复 `stockinsight-production-proxy:m6-validated`，只重建proxy，再运行验证；同步私有env标签防止下次部署反向覆盖。旧镜像保留，数据库不回滚。此回滚路径未在本次实际执行，不伪记为演练通过。无需购买服务器，M6-04原遗留事项不改判。
