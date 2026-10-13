# StockInsight 会话交接

更新时间：2026-10-13，Asia/Shanghai。当前工作目录 `/home/crazychen/myprojects/StockInsight`。

> 最新状态：2026-10-13 已获授权更新前端并合并推送，学习页部署为 `stockinsight-production-proxy:learn-20261013`，实际入口 `https://localhost:18443/learn`（原邀请认证不变），生产浏览器验收通过。Git交付结果见文末最新记录。无运行中匿名代理，不自动开启公网窗口。原M6未验收事项保持。

## 1. 本轮授权与范围

用户明确要求真实数据采集与自动更新跑通，让搜索、K 线、均线、数据状态有实际内容，并完成 M5 全部验收。M6 公网部署、服务器购买、远程推送、tag/Release 未在本轮授权。上一轮 M4 的合并与推送已完成，基线 `main/origin/main` 为 `aa3da56`，本轮在 `feature/m5-live-data-acceptance` 开发。

## 2. 真实运行

- 开发库保留原卷 `stockinsight-local_postgres_data`，revision `0001_initial_schema`；不向开发库写模拟数据。
- 真实目录 5,223 只；真实日线与均线各 732 行。覆盖平安银行 `000001.SZ`、贵州茅台 `600519.SH`、宁德时代 `300750.SZ`、招商银行 `600036.SH`，各 183 个交易日，2026-01-05～10-09。
- 四只股票日期集合与官方沪深 2026 交易日历一致，最新 MA5/20/60 独立复算一致。日线 `akshare_tx`、不复权、元/股/元、UTC 获取时间，MA `sma-close-v1`；贵州茅台最后 MA60 `1291.0760`。
- 首页新增默认采集范围及四只股票入口；股票目录不代表全市场日线。其他股票需手动补采并加入 scheduler 名单。
- db/API/web 仍 healthy、loopback 5432/8000/5173，浏览器 `http://127.0.0.1:5173/`。
- `automation` profile scheduler 已常驻，`restart: unless-stopped`、独立于 API、上海 17:30、启动补最近收盘交易日；当前真实时钟为 10-12 盘前，最近目标 10-09。重启实际 `job_count=0, skipped_jobs=4`，未冒充未来 17:30 已发生。
- 日历 `config/calendars/sse_szse_2026.json` 按沪深全年公告生成，242 日，覆盖至 2026-12-31。到期前更新公告派生清单并重启；覆盖外拒绝采集，不猜测工作日。

## 3. 实现修正与架构

CDR 689 过滤但核心 Validator 不放宽；SDK DataFrame 用 Python 最短往返数字 JSON；显式腾讯接口及真实来源；腾讯金额仅清除两 ULP 内的单位换算尾数，实质分以下输入拒绝；1.19.1 深市 000 股票补一次手转股。东方财富在本网络连续失败，显式选择腾讯成功，不自动改源。

来源由 Provider 声明并经 SourceProvider 校验，Repository 不判断上游。API/Service/Repository 分层、同事务指标和独立调度不变；无 Schema/migration 变化。`--catch-up` 按目标交易日而非本地尝试日期去重，补前日不会阻止当日盘后。ADR-020 记录已授权范围内细化，无核心技术栈/价格口径变化。

Dockerfile 使用版本 constraints，BuildKit `build_proxy` 临时 secret 可选；不以 build args 保存代理。宿主原本缺 Buildx，已从签名 apt 索引包解压到 `/tmp/stockinsight-m5-vm/buildx`；临时 `DOCKER_CONFIG=/tmp/stockinsight-m5-vm/docker-config` 发现 plugin。常驻容器运行不依赖该目录，重新构建需标准 Buildx/Compose 安装或该临时配置。

## 4. 已执行验证

- `.venv/bin/python scripts/test_postgres.py`：最终 **388 passed in 15.79s**，六个新隔离库，含 migration 升降级/再升级、采集 CLI 真实子进程/信号恢复、API/指标/调度，无 skip。测试库保留，不清已有库。
- Ruff 检查和格式通过；前端 `npm run typecheck`、`npm test` **31 passed**，生产构建直接 `npm run build-only` 通过；详情 chunk 602.26KB / gzip206.73KB 警告保留。
- 模拟边界 `npm run test:browser` 与真实数据 `node scripts/browser-live.mjs` 分开；桌面/390px 搜索→详情→SVG/MA→来源/状态页均通过，无浏览器异常。
- 浏览器本机运行库：`PLAYWRIGHT_BROWSERS_PATH=/tmp/stockinsight-browser/browsers`、`LD_LIBRARY_PATH=/tmp/stockinsight-browser/libs/usr/lib/x86_64-linux-gnu`、`FONTCONFIG_FILE=/tmp/stockinsight-browser/fonts.conf`。软件模拟新 Linux 可设置 `STOCKINSIGHT_BROWSER_TIMEOUT_MS=120000`，不修改生产延迟承诺。
- pip-audit 无已知漏洞；启用 TLS 验证的 npm audit 0 漏洞、229 节点。镜像历史实际密码/代理值比对未发现泄漏。最终源码凭据、链接、围栏/Mermaid 结构与 `git diff --check` 在提交前再核验，不冒充 Mermaid 渲染。
- 本机每接口 20 次顺序请求 p95：搜索17.83ms、日线30.59ms、均线32.42ms、任务8.02ms；不作为并发容量承诺。

## 5. 新 Linux 与备份

M5-02 通过：官方 Ubuntu Minimal 镜像 SHA-256 已校验，独立 QEMU TCG、Ubuntu24.04.5、内核6.8.0-146-generic、独立 Docker29.1.3。安装后确认零镜像/容器/卷；不共享宿主 socket。按 README 预构建开发镜像路径导入制品、创建新卷，采集前四表0行，迁移无模型差异，真实采集后5223/732/732/6行、独立调度4项成功、重启跳过4项。HTTP/桌面/手机浏览器及复验通过，49个后端与21个前端运行源码哈希与工作区一致。TCG高峰探测启动误报已用compose.acceptance.yaml的30秒预算修正，保留原HTTP探测，最终三服务healthy。无认证信息的本机代理仅传入host/port，未转移凭据。验收VM正常关闭，磁盘/卷保留；详细结果见docs/M5_ACCEPTANCE.md。

M5-04 通过：GPG AES-256 归档恢复到独立容器 `stockinsight-m5-restore-1bdd7e`、独立卷、loopback15432。备份时四表5223/732/732/13行，revision1行，内容哈希一致；等价 text cast 规范化后约束/索引一致。临时8002只读 API 搜索/详情/行情/指标/任务五项通过，已停止临时 API。原库后来自动调度新增任务，任务数可能大于备份时13，不是丢失。

密钥 `secrets/backup.passphrase`、加密归档 `data/backups/stockinsight-20261011T172650Z.dump.gpg` 均0600、Git忽略。`scripts/backup_postgres.py` 实际输出 `data/backups/m5-script-acceptance.dump.gpg`。明文 dump 未落盘；密钥与归档应异地分开保管。独立恢复实例/卷保留，不自动删除。生产异地/定时/轮转与 RPO/RTO 属于M6。

## 6. 限制与交付边界

stocks 的逐行来源时间仍null，未知状态/上市日期不推断。行情和指标只覆盖4只股票，空响应不证明全覆盖；指标source仅当前日输入。失败任务保留错误，后续成功不抹掉其他任务记录。停牌/目标日缺行仍可见失败，早期缺口需显式 backfill；自动水位不证明全历史完整。

AKShare SDK MIT不授予上游行情公开再分发许可。公开/商业数据展示授权未取得；M5完成的是本地复核，M6需所有者确认许可、认证、HTTPS、最小权限生产账户与运维。本地开发Compose/Vite不直接当生产镜像。目前无需购买服务器。

## 7. 下一步与 Git

**M5-01～05 全部 DONE，v0.1.0 RC 准备完成。**2026-10-12 用户随后明确授权本地合并并推送；`feature/m5-live-data-acceptance` 已快进合并到本地 `main`，功能提交 `e099f20` 与数据源诊断 `c303d95` 已成功推送现有 `origin/main`。当前使用 `main`，最终文档同步提交见Git日志；功能分支保留。不创建tag/Release，M6未启动。前文与第8节“未合并/推送”描述保留为此前验收时点记录，以本节及第9节为当前Git状态。

下一会话可复制任务（仅在用户明确要求公网后）：

```text
继续 /home/crazychen/myprojects/StockInsight，执行 M6-01 部署需求与容量评估。先依次阅读 AGENTS.md、PROJECT_PLAN.md、TASKS.md、SESSION_HANDOFF.md、docs/DECISIONS.md、docs/M5_ACCEPTANCE.md，检查实际Git/服务状态。M5已全部验收，本地4只股票真实数据与scheduler正在运行；保护原库/卷及加密备份。先依据实际数据量、预期访问规模、HTTPS/认证/最小权限/数据公开授权条件形成具体方案，不擅自采购、公开部署、发布Release或清库；合并/推送只按用户的新明确授权执行。
```

验收证据副本在data/acceptance/m5-20261012/（Git忽略）；临时恢复实例已停止但卷保留，原开发db/API/web/scheduler继续运行。


## 8. 东方财富连接复核与服务恢复（2026-10-12）

用户要求解决东方财富无法获取或提供替代方案。本轮东方财富直连/环境代理均HTTP200；项目原有AKShare1.19.1 Provider→Validator对600519.SH、000001.SZ各183条真实日线通过，腾讯同区间同样通过。此前失败当前不可复现，未查明历史网络根因，不将无需的SDK升级、登录Cookie或TLS降级当修复。新增scripts/diagnose_market_data.py和docs/MARKET_DATA_DIAGNOSTICS.md，提供安全只读探测、错误分类、来源显式切换及Tushare官方文档方案；Tushare未接入/未实测。

另发现原db/API/web容器退出（255），scheduler反复scheduler_storage_error；已执行docker compose start db api web恢复原容器/原卷。该现象与当前行情HTTP可达性独立，未证实退出根因。常驻来源仍腾讯，不覆盖现有行情，不自动清除失败任务。后续切换来源重采会更新重叠日期来源，既有成功任务不会自动失效，详见诊断文档。

本轮Provider/Transport定向测试56 passed；Ruff及诊断脚本格式检查通过。诊断仅只读网络/校验，不新增Schema、依赖或业务采集行为。M5仍DONE，M6未启动；本轮本地提交，未合并或推送。

最终复核：scheduler容器内东方财富沪深两样本各183条通过；db/API/web均running/healthy，scheduler running并输出succeeded、skipped_jobs=4、failed_jobs=0、target_date=2026-10-09。诊断异常链含循环与带凭据异常的脱敏断言通过；改动文档链接、代码围栏、当前数据库密码/私钥检查和diff检查通过。


## 9. M5 合并与远程同步（2026-10-12）

用户明确授权本地合并并推送。fetch确认本地main与origin/main均为aa3da56且无分叉，工作区干净；推送内容35个源码/文档文件通过当前密码、私钥及运行数据排除检查。执行git merge --ff-only feature/m5-live-data-acceptance后，git push origin main已成功将aa3da56更新至c303d95。当前提交同步交接/任务/CHANGELOG，继续按本次授权推送；最终完整SHA以Git日志与远程核验为准。功能分支保留，无强推、标签、Release或公网部署。

本次定向命令`.venv/bin/python -m pytest backend/tests/test_market_data_provider.py backend/tests/test_akshare_transport.py backend/tests/test_scheduler.py -q`为66 passed in 1.60s；`.venv/bin/ruff check backend scripts/diagnose_market_data.py scripts/backup_postgres.py`通过，整个待合并diff检查通过。快进不产生额外业务改动，未重复完整数据库/前端验收，先前388/31项及真实Linux/备份/浏览器证据保留。架构与数据库不变。目前无需购买服务器；下次仅按用户授权执行M6-01，复制任务见第7节。


## 10. 股票信息展示优化（2026-10-12）

用户反馈搜索/详情重复未知及技术文案难懂，授权优化展示。当前分支feature/readable-stock-information，基于main 2cf6ff7；仅前端展示，无API/Schema/采集/算法或架构变更。搜索按当前页是否存在已确认状态决定状态列，保留真实已知状态；详情仅展示已存在基础字段，缺失合并一条说明，不假设上市/停牌。市场/行情来源中文化，实际返回行情范围及获取时间限定当前显示数据；不复权、时间语义及原始source、均线版本/来源边界放原生details。均线表中文名称与历史不足解释，tooltip中文来源；精确数值不变。

Node22下npm run typecheck、npm test（35 passed）、npm run build-only通过，保留604.23KB/gzip207.55KB详情chunk提示。npm run test:browser模拟搜索/日期/缩放/截断/空/错误/重试及手机通过；node scripts/browser-live.mjs真实贵州茅台183条、MA60 1291.0760、搜索/均线/展开说明/桌面手机/状态通过，无pageerror。截图目视复核手机布局通过。未重复后端数据库测试，因为没有后端改动；原388项证据保留。

临时浏览器PLAYWRIGHT_BROWSERS_PATH=/tmp/stockinsight-ui-browser，LD_LIBRARY_PATH=/tmp/stockinsight-ui-libs/root/usr/lib/x86_64-linux-gnu，FONTCONFIG_FILE=/tmp/stockinsight-ui-libs/fonts.conf；只解压运行库/字体，无系统安装。新的截图副本在data/acceptance/readable-ui-20261012/（Git忽略）。原服务/卷及腾讯来源保留，刷新http://127.0.0.1:5173/可查看。本轮本地提交，未合并/推送，未启动M6、未采购。先前第9节已同步状态仅适用于2cf6ff7之前交付；本轮新功能仍待另行合并同步。

下一会话可复制：核对StockInsight的AGENTS/规划/任务/交接与Git状态，检查feature/readable-stock-information的前端展示优化；保持真实基础资料缺失提示和可追溯行情说明。如用户要求补齐上市日期/状态，先设计真实基础资料采集及source/fetched_at持久化，不以网页隐藏替代数据采集完成，不根据行情猜测上市状态；M6按新授权启动。


## 11. 网页来源策略和使用教程（2026-10-12）

用户明确要求网页控制来源或东方财富优先/腾讯备用，并新增首页使用教程。当前分支feature/source-policy-and-guide，基于前轮22249f5；保留前轮展示优化，M6未启动。ADR-021记录授权范围内细化。新增本地GET/PUT /system/source-policy，Router→Service→配置文件Repository（原子替换/锁/revision），无业务DB变更。production写入403；development限定本机Origin/Host及LOCAL_ADMIN_TOKEN，自定义Web端口暂不支持管理写入。口令仅API环境注入，前端密码框提交后清空，不进构建/localStorage/日志。

API可写、scheduler只读共享data/source-settings；配置不存在默认prefer_eastmoney，损坏/不可读显式失败。来源策略每股采集读取，新设置不重采历史/不清成功任务/不扩大股票名单/不立即重试当天已尝试失败。PolicyProvider处理请求/数据错误、空、调度目标未就绪时备用腾讯，真实来源传递经ReadyProvider/SourceProvider动态检查，Repository不判断上游；数据库或程序错误不触发备用。安全日志保留原因和最终来源。

本地已运行scripts/init_source_settings.py，在私有.env生成LOCAL_ADMIN_TOKEN，secrets/source-admin.token为0600且Git忽略；使用现有镜像--no-build重建API/scheduler配置，原库/卷不变，仅新共享目录经容器root调整为应用UID10001可写及750。README提供新环境操作。首次初始化曾因Path.open不支持opener失败，已改为标准open并成功重跑；未输出口令。

首页/guide教程按搜索/K线/均线/来源/更新说明真实4只范围，首页/source-settings设置页面支持三策略。真实浏览器验证错误口令401、三模式保存刷新持久化、口令清空/无localStorage、教程导航、桌面/390px无溢出；当前最终模式prefer_eastmoney、revision3。调度容器真实两只600519.SH/000001.SZ均先请求东方财富失败后备用腾讯，各183条2026-01-05～10-09通过日历/Validator，source akshare_tx；只读验证未覆盖原行情。自动daemon启动检查succeeded/skipped4/failed0，db/API/web healthy、scheduler running。

最终全新六隔离库scripts/test_postgres.py为399 passed in13.63s，无skip（最初397passed/2failed为原OpenAPI路径集合未包含新增配置接口，更新契约后完整复跑通过）；非提升权限测试因子进程/线程环境限制中断，不作为通过证据。前端typecheck、38passed、生产构建通过，保留604.26KB/gzip207.57KB详情chunk提示。实际网页管理测试browser-settings.mjs通过；原mock边界browser-smoke.mjs及真实数据browser-live.mjs复验均通过（183条、MA60 1291.0760），无浏览器异常。Ruff/78文件格式检查通过，最终文档/源码/敏感信息检查在提交前核验。

当前仅本地提交，不合并/推送。管理口令由本机终端cat secrets/source-admin.token取得并粘贴网页，本轮不分享口令值。无需购买服务器或进入公网。下一会话可复制：按AGENTS读取项目文档并核对Git和服务；检查feature/source-policy-and-guide的来源设置/教程和真实来源日志。如需即时网页补采，另行评审后台任务入口、授权、防重与失败恢复，不在请求内同步执行网络采集；合并/推送按用户新授权。

## 12. M6-01 部署需求与容量评估（2026-10-12，当前）

用户要求进入M6部署需求与容量评估，并确认首期2–10名同时使用的受邀用户、约100股、先评估成本。已从干净的feature/source-policy-and-guide（f67b011）创建feature/m6-capacity-assessment；保留前两轮页面/来源功能，不切回main丢弃这些功能。M6-01 DONE，M6-02～04 TODO；未经授权没有扩大采集、购买、部署、合并或push。

交付docs/M6_CAPACITY_ASSESSMENT.md与只读scripts/benchmark_queries.py：限定loopback、禁环境代理/重定向、四类GET、1/4/10并发各80次测量，240次成功/零错误；10并发p95为搜索200.11ms/日线210.52ms/均线200.38ms/状态192.29ms。样本为开发服务/热缓存/短时/原4股，不代表100股或2核4GiB生产容量。证据JSON在data/acceptance/m6-20261012/，Git忽略。

数据库READ ONLY测量：9,247,767bytes，stocks5223、daily_prices732、indicators732、jobs14；4股日期2026-01-05～10-09，revision0001_initial_schema。空闲Docker stats四服务约572MiB，宿主4逻辑CPU/7.76GiB，未模拟候选规格。逻辑pg_dump只写内存后丢弃，92,383bytes/0.347s，未恢复/写入原库。当前db/API/web healthy、scheduler running，宿主端口仍全loopback；原卷、加密备份、来源设置保留。

报告给出100股存储/串行采集/全历史指标重算模型与2核4GiB/80GiB待验证候选；官方价格参照VPS24美元/月+对象备份5美元/月，域名/税费/超额流量另计；只作预算参照，未选供应商或确定区域库存。数据许可、预算/地域/域名、名单/起点、运维与恢复目标仍待确认。ADR-022 Proposed记录Caddy/统一受邀认证/生产账户与备份运维方案，不改已批准项目基线、架构图、栈或Schema。

实际验证：`.venv/bin/python scripts/benchmark_queries.py`成功；`.venv/bin/ruff check scripts/benchmark_queries.py`及`ruff format --check`通过；文档内部链接/围栏、敏感信息模式、git diff --check与提交内容检查通过。未重跑业务后端/前端/migration：本轮没有修改业务代码或Schema；上一轮399项后端及38项前端为历史证据。Docker/socket和本机网络访问在sandbox内受限，通过仅测量用途的提升权限运行；无服务/配置修改。

本轮形成范围单一的本地提交（SHA以Git日志为准），不合并/push；main/origin/main的本地跟踪引用仍2cf6ff7，本轮未fetch或核验GitHub当前状态，不能声称远程实时一致。当前分支包含尚待同步的展示优化22249f5与来源功能f67b011。当前无需购买服务器，后续合并/推送须用户新授权。

下一会话可复制：

```text
继续 /home/crazychen/myprojects/StockInsight，按AGENTS依次读项目规划/任务/交接/决策及docs/M6_CAPACITY_ASSESSMENT.md，检查Git和实际服务。M6-01完成，首期2–10名受邀用户/约100股；当前仍原4股库。先核对用户对ADR-022及预算/地域/域名、名单/历史起点、数据用途许可和恢复目标的决定；获确认后开展M6-02/03的本地可审阅生产配置与隔离演练。保护原卷/备份，不采购或公网部署、不扩大名单、不合并/push，除非另获明确授权。当前feature/m6-capacity-assessment包含尚未合并main的两轮页面/来源改动，保持完整历史。
```


## 13. M6生产实现与本地完整运维演练（2026-10-12，当前）

用户要求“把整个m6运行完毕”，授权ADR-022方案实施；询问公网部署所需服务器、域名、异地目标和数据展示授权时，用户回复“暂无”。已完成全部可独立推进的本地生产实现与演练；M6-01/02/03 DONE，M6-04公网部署仍TODO，不宣称整个M6完成。无采购、创建资源、公开部署、merge、push、tag或Release。

当前feature/m6-production-deployment基于157c01c，保留22249f5/f67b011前端与来源功能；main与本地origin/main仍2cf6ff7，本轮没有fetch/远程核验。实现提交标题`feat: add production deployment and operational acceptance`，完整SHA以git log为准。原开发stockinsight-local/原卷保留，不扩采开发库。

生产文件：compose.production.yaml独立项目，deploy/Dockerfile.{backend,proxy,operations}，Caddy HTTPS/静态SPA/逐人Basic Auth/所有API认证/禁写/脱敏轮转；DB bootstrap四类最小权限角色；应用非root/只读根目录/资源上限；scheduler配置转换复用既有CLI；operations.py实现GPG流式加密、严格SSH传输/远端哈希、每日备份/7日4周本地保留、独立空库恢复、监控/HTTPS告警。scripts含私有初始化、邀请管理、显式发布/回滚、严格HTTPS检查和并发测试。生产前端构建仅只读，开发管理功能仍存在。没有业务Schema、核心栈、价格/单位/指标算法变化。

本机项目stockinsight-m6，仅127.0.0.1:18080/18443；入口https://localhost:18443，凭据secrets/production/preview_password，不在报告中给值。浏览器需信任演练CA，严格验证脚本使用secrets/production/local-ca.crt。APP镜像m6-local、PROXY镜像m6-validated、OPS镜像m6-final，最终不可变ID在data/releases/20261012T032825Z-0358b258.json，completed；生产外发应重建/标记实际提交SHA。生产API/DB无宿主端口。全部M6服务cpuset0,1，单容器内存上限，不等价独立4GiB主机；当前宿主7.76GiB有开发服务竞争。

真实100股容量样本config/universe/preview-100.json（原4股+目录升序96股），复制到私有配置。初始只读复制开发目录/行情/指标，未复制开发任务；随后新库串行采集5分50.378819秒，99成功/1失败000016.SZ daily_data_not_ready，日线/指标各18106，目录5223，任务100，revision0001_initial_schema；源库15,875,095bytes。未猜测失败股票停牌/上市原因。scheduler常驻，启动跳过99成功股并重试失败股仍失败；不声称未来17:30触发已验证。开发库保持原4股732/732。

最终验证：backend scripts/test_postgres.py六新库399passed/13.33s；frontend Node22类型/39tests/镜像内生产build通过；deploy/tests 18passed；Ruff/格式通过。严格CA/主机名与HTTP301正确HTTPS端口、认证/SPA/只读共11项通过。新增colleague认证200，撤销后401而preview仍200。API实际UPDATE被拒绝；api/worker/backup权限与si_owner表owner已核验。browser-production.mjs真实搜索/K线/均线/失败任务/只读设置/教程，桌面和390px手机通过，0pageerror，截图目视检查，无横向溢出。UI浏览器仅本地context允许测试证书，证书可信性证明来自独立Python严格校验。

15分钟混合维护负载：901.02秒/26019请求/51失败0.196%/成功请求p95 19.52ms；期间采集、备份和邀请撤销/proxy重建，严格零错误脚本退出1，如实保留失败结果。最终60秒稳定复验60.92秒/1725请求/0失败/p95 38.64ms，退出0；不冒充15分钟零错误。容量只为本机演练，非VPS承诺。

备份接收器deploy/acceptance/transport.compose.yaml为同机无发布端口的独立SSH/HTTPS容器和卷；严格known_hosts与专用证书/密钥，绝非真实异地。最终100股备份658732bytes/1.681s，remote_verified true只证明传输哈希。新建stockinsight_capacity_restore恢复0.422s；deploy/acceptance/verify_database.py四表5223/18106/18106/100逐行SHA256完全一致。原4股快照另恢复stockinsight_m6_restore，三表哈希一致。两恢复库均保留，不覆盖原库。密钥/归档分开保管，RPO24h/RTO2h仍为需目标主机实演的目标。

错误备份密码实际退出1，旧成功回执不变、0partial，HTTPS接收端收到backup_failed。monitor --once当前预期退出1：market_data_stale和tls_monitor_unconfigured，接收端实际收到。最终monitor样本p95 11.93ms/5xx0、磁盘16.86%、宿主内存64.43%；无公网域名不能关闭告警假装通过。日历覆盖到2026-12-31，提前30天提示更新。

实际发布故障：专用overlay把M6 API命令改为退出1，rollback根据data/releases/20261012T032539Z-72bc6985.json的旧镜像ID恢复，核心查询及原10项HTTPS检查通过；之后重新发布最终镜像并启用scheduler/backup常驻。schema变化拒绝回退有单测，不做隐式downgrade/清卷。测试overlay为monitor/backup增加测试告警CA；正常release不自动加载overlay，后续本地复验需两个-f，避免测试自签回调失去信任。

证据data/acceptance/m6-production/与data/releases/均Git忽略；secrets/production/、secrets/m6-transport/和真实.env.production不进Git。Docker volumes保留备份/生产/SSH测试接收器状态。运行手册docs/M6_PRODUCTION_RUNBOOK.md与报告docs/M6_ACCEPTANCE.md为后续入口。构建临时DOCKER_CONFIG=/tmp/stockinsight-m6/docker-config，官方Buildx0.38.0 SHA256已核验，Caddy官方registry manifest/blob校验后导入；没有系统安装/daemon配置修改。Python/apt直连官方HTTPS构建，npm可用BuildKit代理secret；不关闭TLS验证，不输出代理或口令。临时工具失效时按标准安装路径另行准备。

下一会话可复制：

```text
继续 /home/crazychen/myprojects/StockInsight 的M6-04。按AGENTS顺序读取规划/任务/交接/ADR，再读docs/M6_PRODUCTION_RUNBOOK.md和docs/M6_ACCEPTANCE.md，检查Git及两个独立Compose项目。当前M6-01～03已实现/本地演练，M6-04暂无服务器/域名/异地目标与行情展示用途确认。保留原开发库及全部演练/恢复卷、失败任务和加密备份；先核对用户新提供的目标资源，按预检→备份→显式migration→发布→真实公网HTTPS/邀请撤销/100股/持续并发→真实异地恢复→回滚验收推进。不得把同机SSH副本当异地或本机资源测试当实际VPS验证；采购、merge/push及Release仅按新的明确授权执行。
```

是否购买服务器：本地演练无需新增资源；要完成M6-04需已有或经用户批准购买的Linux主机、域名与真正异地备份。是否同步GitHub：需要，当前只本地提交，等用户明确授权merge/push。


## 14. Cloudflare Tunnel阶段A/B（2026-10-12，当前）

用户决定暂不购买VPS，优先现有Ubuntu主机；本轮只授权A环境/安全预检和条件满足时B独立静态Quick Tunnel。明确禁止StockInsight公网映射、修改既有HTTPS/认证/代理、停止/重建容器、数据库变更、使用生产token、系统级安装、Git commit/merge/push。详情见docs/M6_TUNNEL_FEASIBILITY_20261012.md；原docs/M6_ACCEPTANCE.md及失败记录保留。

实际环境Ubuntu24.04.3/x86_64/4CPU/7.8GiB（当时可用2.6GiB），WSL2内核6.6.87.2-microsoft-standard-WSL2，Linux根卷约786GiB可用（不代表Windows物理余量）；Docker29.1.3/Compose2.40.3，active/enabled。11个running容器、2个历史stopped，保留；StockInsight开发127.0.0.1:5432/8000/5173、演练127.0.0.1:18080/18443，演练DB无发布端口且internal网络。默认沙箱netlink禁止，通过现有用户宿主权限上下文只读Docker/ss，无sudo或系统修改。

Caddy运行文件与deploy/Caddyfile哈希一致；当前内部CA/localHost TLS在Caddy443终止，HTTP18080跳转https://localhost:18443。全部业务HTTPS路径先Basic Auth；内部API无全站邀请认证、禁止把Tunnel直接指到8000或5173。未带凭据13路径均401，使用公开CA证书严格校验，无邀请密码/生产私钥参与。uvicorn代理头信任*、Caddy原Host/localhost重定向与公网不一致，需要正式方案另审；Axios同源相对/api/v1，未找到业务Cookie/CORS/WS/SSE实现，不以此推断未来Access无需测试。

cloudflared原未安装，按官方文档从Cloudflare GitHub release2026.10.0取amd64独立二进制到/tmp/stockinsight-quick-tunnel-1qisi_g3/cloudflared，40129756bytes，官方SHA256 d33ff2d14475178d2012c2c56beba87389ac5ded27649519f198a7d3134a99db完全一致；没apt安装、改PATH、注册service或登录Cloudflare。第一次TLS EOF后保持验证重试成功。官方API/包仓库/GitHub HTTPS可达，Quick API GET405仅证明方法受限；边缘DNS/IPv6 TCP7844可达。额外通用Python IPv4 TLS探测SSLCertVerificationError未判通过，原因未确证；cloudflared自己的region1/2 QUIC和HTTP2预检成功，实际QUIC注册成功才是本轮隧道证据。

新增deploy/acceptance/quick_tunnel.py仅标准库、loopback内核分配端口、固定JSON、不导入业务/不连接DB/不读取生产配置；cloudflared空HOME/受限继承出站proxy/日志脱敏、metrics仅loopback、最多600秒、STOP或中断清理自身子进程和HTTP。已实际注册QUIC（12:41:40北京时间），测试127.0.0.1:45735，临时URL https://knows-offerings-ocean-perl.trycloudflare.com，test_id38a271899ac04066a0a52d478781d0ad，stockinsight_connected=false。Python严格HTTPS及本机Chromium未忽略证书错误均200/正文一致；公网/api/v1/stocks、/.env、/docs、/unknown均404。ICMP普通用户权限警告不影响HTTP，未改sysctl/组权限。远端web工具不能访问该临时域名，不算外网成功；已给用户手机关Wi-Fi蜂窝验证步骤，等待人工结果后清理（或600秒自动到期）。清理/外网最终状态以下续记为准。

文档新增独立M6报告、ADR-023（仅A/B Accepted，正式映射未批准），更新TASKS/交接/规划/DEPLOYMENT/CHANGELOG入口；原生产配置及M6验收文件不动。原18项运维测试18passed/0.07s，新脚本Ruff/格式通过，新增报告链接/围栏/代理凭据检查及git diff --check通过。所有运行证据data/acceptance/m6-tunnel-20261012/ Git忽略，不保存生产密码/私钥/Cloudflare凭据。当前分支/HEAD保持4496600，本轮无git add/commit/merge/push。

后续必须等待用户确认正式业务映射范围；评审账号/托管域名/免费Access邮件白名单/源站认证、三段TLS（caPool/SNI/Host，不关闭校验）、可信代理头/客户端IP/HTTPS重定向、WSL/Windows休眠和重启/重连、真实异地备份和灾备、采集99/100及混合维护51失败。Quick Tunnel无SLA、临时域名、200在途/SSE限制，不作为M6-04通过或部署永久免费承诺。当前不需要买VPS；固定公网域名可能需用户提供/购买（另授权），账号和任何token由用户自行私下管理，不发送聊天。

下一会话可复制：

```text
继续StockInsight的Cloudflare Tunnel分阶段评估。按AGENTS顺序读取规划/任务/交接/ADR，重点docs/M6_TUNNEL_FEASIBILITY_20261012.md及原M6_ACCEPTANCE/PRODUCTION_RUNBOOK；检查HEAD4496600后本轮未提交文档/独立脚本，保留用户工作区。先核对上轮测试进程及清理证据/手机外网反馈，若未完成只重做明确授权的静态隔离验证。StockInsight业务未获公网映射授权，不修改原Compose/Caddy/认证，不重建/停止原容器，不碰DB/生产密钥，不commit/merge/push。正式映射仅先形成可审阅的账号/域名/Access、TLS/Host/代理头、WSL持续运行与真实灾备方案，再等待用户确认。
```


第14节最终补记（12:52，Asia/Shanghai）：限时窗口未收到手机蜂窝外网反馈，保留TODO，不以host-side浏览器或远端工具无法抓取替代外网验收。测试自动结束，日志12:52:03 Tunnel/metrics stopped；12:52:35实际核验PID258452不存在、HTTP45735和metrics45289关闭、旧URL返回HTTP530且无测试test_id，父脚本退出0。初次提前检查状态尚未写完曾返回Test still running，未判通过，最终已重新完整核验。原13容器（11running/2stopped）的ID/StartedAt/RestartCount/镜像/端口/网络、部署文件和私有env SHA256前后完全一致，生产DB仍Internal=true。未有残留测试后台进程，原业务运行不受影响；临时官方二进制约38MiB保留/tmp供后续明确窗口复验。TASKS分开标记A及B程序清理DONE/B外网人工TODO，M6-04与原失败项不变。最终Git为6个治理文档修改+2个新增（独立报告/脚本），暂存区空，HEAD4496600不变，未commit/merge/push；下一步先约定外网人工复验或仅评审正式业务方案，仍不能直接映射StockInsight。


### 隔离测试重新开启（2026-10-12 13:12，Asia/Shanghai）

用户明确要求“重新开启”。复查原11个运行容器仍在运行、原业务端口保持loopback，旧测试进程不存在；官方临时二进制SHA256复核一致。使用原隔离脚本及独立新证据目录 `data/acceptance/m6-tunnel-20261012/quic-retry-1/`，不覆盖首次证据。新服务仅127.0.0.1:46191固定JSON，QUIC已注册，主机侧严格HTTPS返回200且正文一致。临时URL为 https://anyone-missing-drew-syndrome.trycloudflare.com ，test_id=e640da55f33c489ca626285fe2ba7eac；已说明手机热点情景可以验证，等待手机蜂窝浏览器实际反馈，不能预先标为通过。窗口最长600秒，约13:22自动清理；收到反馈可通过该目录STOP文件提前清理。业务映射未授权，本轮无系统安装、生产配置/数据库操作及Git提交。最终外网反馈与清理情况以后续补记为准。


### 重新开启窗口最终结果（2026-10-12 13:14，Asia/Shanghai）

用户明确反馈手机访问“访问成功，内容一致，无证书警告”，阶段B人工外网浏览器验证完成。收到反馈后写入本轮证据目录STOP文件，脚本实际退出0；13:14:30核验owned_process_alive=false、local_port_closed=true，临时公网URL返回HTTP530且不含测试test_id，确认入口已失效。原11个运行容器仍在运行、API/DB/web健康，业务loopback发布端口保持原状。未操作原服务、数据库、生产配置或Git提交；测试二进制文件保留/tmp，测试进程不保留。证据在data/acceptance/m6-tunnel-20261012/quic-retry-1/state.json及cleanup.json。TASKS仅将阶段B人工外网子项更新DONE，首次窗口未反馈证据不覆盖，M6-04和真实异地备份/混合维护失败项不变。后续仅评审StockInsight正式映射前置条件，等待用户单独确认，不自动开放业务。


## 限时业务公网试用补记（2026-10-12）

用户明确“授权业务公网试用”，ADR-024接受仅此范围；现有主机一小时Quick Tunnel，严格校验源站HTTPS，沿用原Caddy邀请认证/只读入口。独立启动脚本deploy/acceptance/business_tunnel.py、严格TLS浏览器frontend/scripts/browser-tunnel-trial.mjs、报告docs/M6_BUSINESS_TRIAL_20261012.md。不修改原生产配置或既有容器/数据库，不注册账号/购买/安装系统软件，不commit/merge/push。原M6失败项保持。具体结果及当前URL以后续最终补记和证据state.json为准；初始三个窗口关闭且失败证据保留，第四窗口有限重试后继续门禁。


### 最终交付状态：业务试用已开启

本轮第四窗口QUIC注册成功，公网地址 https://eyed-toll-chairs-resolutions.trycloudflare.com ，源站https://localhost:18443；证据trial-4/state.json。公网门禁23项通过：12条未认证路径401、伪造代理头请求拒绝、认证后页面/API/真实行情查询200、docs/openapi404、source-policy PUT403。保持源站CA/主机名校验与公共HTTPS校验，未关闭TLS验证。源站11项检查通过。

浏览器首次使用系统Node18时因Playwright要求Node20+未运行；改用已有Node22.23.1，无系统安装。严格公共证书验证的Playwright真实搜索贵州茅台、K线/均线、只读设置、失败任务可见、教程、桌面/390px手机布局通过，无页面脚本错误；截图及browser-probe.json在本轮Git忽略证据目录。已向用户提供手机蜂窝登录步骤，业务外网人工反馈待取得，不能以旧静态测试反馈替代。

限时窗口从13:23:45计时，预计北京时间14:23:45自动关闭。当前Tunnel按用户授权保持运行供试用，尚未到期，不把关闭结果预先标通过；提前关闭命令见上文STOP步骤。此窗口不承诺永久地址/稳定可用；重启会换URL。实际记录URLError有限重试恢复，稳定性风险保留，最终门禁全部通过并不抹去原失败窗口。

原13容器ID/启动时间/restart/镜像/端口/网络和部署及私有env哈希前后完全一致，生产DB仍Internal=true。仅业务GET验证与代理入口拒绝的PUT，没有数据库管理操作、采集扩容、Schema或数据迁移；服务既有正常日志与后台调度仍可自行写入。不改原M6_ACCEPTANCE/PRODUCTION_RUNBOOK或Caddy/Compose，不提交/推送/合并Git。

下一会话：先读取AGENTS规定文档及docs/M6_BUSINESS_TRIAL_20261012.md，检查trial-4/state.json和手机业务反馈，确认限时Tunnel进程是否仍活跃；到期后严格核验旧URL不再返回业务。不自动续期开启，不改原容器/DB/部署配置，不commit/merge/push。受邀他人需独立账号和私下交付，不群发所有者preview密码。M6-04/异地备份/维护失败继续保留。


### 手机业务反馈（2026-10-12 13:28，Asia/Shanghai）

用户明确反馈“登录成功，搜索和 K 线正常”，完成本轮手机外网业务功能验证。此回复没有单独再次说明证书警告，严格公共证书正常仍引用本轮程序及浏览器实测，不扩写用户反馈。证据trial-4/external-feedback.json。当前窗口仍按原授权保留至14:23:45自动关闭，不提前停止，不自动续期；窗口清理和入口失效核验尚待到期，M6-04与原失败项不变。原服务/配置/数据库无新增操作，Git无提交/推送。


## 当前交付评审与8小时匿名启动（2026-10-12，替代前轮下一步）

用户要求检查未修复问题，若没有则合并main并推送；追加明确要求公网8小时且无需登录。当前仍有100股99/100未就绪、混合维护51失败、真实异地备份/长期运行未验收，因此不声称无问题，不根据附条件指令自动合并/推送。新增docs/V0_1_DELIVERY_REVIEW.md具体列出限制；docs/LOCAL_SERVER.md和根目录stockinsight.sh提供当前现有WSL主机启动/public/status/public-stop，默认28800秒。匿名入口采用独立临时Caddy/公开CA，只连接ingress网络、不挂生产密钥，源站TLS严格验证、写方法403、隐藏/调试/未知API404，原localhost18443认证保留。

匿名公网启动经自动审批被拒绝，理由是需具体确认将业务行情/任务数据发送至运行时生成的公共目的地；没有绕过。仅执行--local-only：19项查询/禁写/路由/严格源站CA检查通过并清理本轮容器，无匿名公网URL。初始本地镜像能力与tmpfs CA复制适配失败已修正，保留NET_BIND_SERVICE及读取公开CA、不安装信任，精确owner标签清理，失败资源已清理。cloudflared复制到data/tools固定官方digest，不依赖/tmp，不系统安装。

本轮完整回归399后端/39前端/18运维均通过，Node22类型/构建通过（604KB详情chunk提示保留），新脚本Ruff/bash语法通过。全新6个隔离测试库保留，原业务库不变。实际远程main通过ls-remote核验为2cf6ff7a3024a4f90fd52f88d047423121f4b8c2；本地当前feature/m6-production-deployment HEAD4496600，未提交/合并/push，本轮工作区继续保留。不购买资源。前一带认证窗口已到期，state process_stopped=true，最终失效核验补记为准。

下一步等待两个明确决定：（1）是否接受docs/V0_1_DELIVERY_REVIEW.md列出的已知限制，以功能首版合并main并push origin；（2）是否允许具体行情目录、日线K线、均线、任务/来源状态通过随机trycloudflare.com地址匿名公开8小时。拿到决定后先核对本轮最新文件/审批范围，不自动把M6-04/旧失败项标DONE。未得到匿名批准时可继续本地start及local-only，不自动执行public。

## 剩余问题处理与匿名窗口（2026-10-12，替代前轮下一步）

用户明确“暂不合并，先处理剩余问题”，并对股票目录、日线K线、均线、任务/来源状态及运行时trycloudflare.com匿名HTTPS目的地明确允许8小时。追加授权后审批通过，当前URL https://programmer-lectures-expert-epa.trycloudflare.com ，本轮北京时间15:37:08～23:37:08。19公网门禁和严格公共证书Playwright桌面/手机真实业务通过，用户对无需登录/证书/搜索/K线复验反馈“正常”；证据public-20261012-153706-9b4be779。当前窗口保持运行，不延长，不预记到期清理成功；提前 ./stockinsight.sh public-stop。

000016.SZ缺数据已确认来自官方停牌，9月4日起，核验登记到10月13日；真实上游158条至9月3日通过严格ReadyProvider。有限登记器用于调度与监控：新scope保留旧failed行，不填停牌日，不改Schema/数据价格口径。后端最终407passed/16.18s，运维22passed/0.09s；先前前端39/typecheck/build通过仍有效（本轮未改前端业务）。app/ops新候选镜像与非敏感manifest/env/独立scheduler配置准备，Compose config校验通过，尚未应用原服务。首次ops导入暴露3.11/3.12语法依赖已修正并隔离验证。

原保护要求禁止停止/重建既有容器及使用生产密钥；因此已向用户请求仅更新scheduler/monitor及正常补采真实000016历史行情的针对性例外授权，等待回复，不能擅自应用。具体候选、回退和资源阻塞见docs/M6_REMEDIATION_20261012.md。现有业务仍99股、原报警不抹去；13个原容器ID/启动时间/镜像/端口/网络/原配置哈希15:50核验全部不变，DB仍Internal=true。

独立匿名代理新增目录挂载配置预验证/原子替换/USR1热加载，admin保持off。15分钟10读者/3次真实响应头改变演练进行中，3次已确认生效且ID/PID/start/restart不变；最终负载结果以后续补记为准。仅此代理配置维护场景，目录前100股，与原采集/备份/邀请撤销/API发布完整混合场景不同，原51失败不改判。

真实异地目标与可信访问配置、Windows休眠/断电恢复窗口尚缺，不能把同机测试或代码修复标为这些真实验收通过；暂不需要采购VPS。旧带认证窗口已停进程，外部复核URLError/DNS错误，未取得HTTP状态，不声称530。

Git继续feature/m6-production-deployment HEAD4496600，暂存为空，未commit/merge/push。读根stockinsight.sh和docs/LOCAL_SERVER.md了解启动；当前现场候选镜像/运行数据不在Git。下一会话先核对本轮STOP/state、用户针对两容器更新的回复、15分钟最终证据；已授权才按候选方案应用并验证原failed保留。不可自动合并、推广固定域名或改变原生产代理/数据库。

维护复验最终补记：15分钟样本900.84秒/26,037请求/1连接异常status0/p95 16.81ms，严格脚本退出1，未达到零失败。3次热加载生效、容器进程不变，最终源文件恢复并reload退出0。该失败样本缺异常类与时间，不能断言根因；新load_production记录最多20条脱敏error_samples，90秒密集热加载复现在独立reload-diagnostic目录执行中，结果以后续补记为准。原M6混合维护51失败仍未解决。

诊断最终补记：90.69秒/2610请求/3次RemoteDisconnected/p95 21.89ms，异常在3.335/51.330/84.352秒，与3/51/84秒reload对应。28次reload均生效且容器进程不变，源文件已恢复。当前单代理热加载仍有连接关闭，不宣称维护零失败，也不以重试掩盖严格指标。后续需评审维护窗口或双实例滚动方案并隔离复现完整混合场景，未自动改拓扑。

针对两容器更新的用户回复是“这次修改是什么意思”，已解释停牌日期判断、补真实历史、不造日线/不删失败行，以及scheduler/monitor作用；这不是授权，候选更新仍未执行。下一次应等明确同意后操作，不能将该询问视为取消保护要求。

### 针对性更新最终补记（2026-10-12 16:07，优先于上文待授权状态）

用户在询问含义并得到解释后明确“可以执行更新”。已仅重建scheduler/monitor为不可变候选镜像，带原transport告警CA overlay与独立halt配置；原.env/私有scheduler.json不改。调度结果1新任务成功/99跳过，为000016补158真实历史至9月3日，覆盖100股、日线/指标各18,264行。旧10月9日failed任务仍在，新增9月3日scope成功；schema仍0001_initial_schema。重复--once0任务/0失败/100跳过，101行任务逐字段不变；原HTTPS11项和匿名公网新增158条通过。monitor重跑market_data_stale消除，仅tls_monitor_unconfigured保留（故monitor --once退出1，不视为全部运维通过）。

更新前完整快照辅助查询因多行json_agg解析失败，组合命令未按预期停止，仍执行了已授权更新；已向用户说明，之后全部变更命令set -e。拆分/紧凑jsonb查询成功，不是权限问题。首次更新前逐字段比较缺证据，不伪造；隔离集成覆盖保留失败行，运行时旧failed仍存在且重复tick101行不变。更新前备份回执11:30为同机验证，不称真实异地/新增数据已备份。

16:07核验仅两个获准容器ID改变，其他11个原容器及原配置哈希不变，DBInternal=true，原告警CA保留。候选manifest.deployed=true。新镜像/独立配置在本机持久Git忽略路径，日常stockinsight.sh start保留当前容器版本；不要清理halt-scheduler.json和halt-candidate.env。正式Compose维护须带transport及halt overlay，仅所需服务，避免全量release回到旧镜像。停牌登记到10月13日，之后须复核新公告，不无限期屏蔽异常。

当前匿名URL及23:37:08到期时间不变，未延长。原51失败及本轮热加载1/3次连接失败未解决，ADR027仅提案；真实异地与WSL恢复缺资源/人工窗口。Git仍feature/m6-production-deployment HEAD4496600，未commit/merge/push；用户暂不合并持续有效。下一会话先核验窗口实际到期清理及当前服务状态，再评审维护连接断开方案和真实备份/恢复资源，不自动扩大部署或合并。

## 用户接受限制并授权main交付（2026-10-12，最新决定）

用户明确“就这样吧，其他问题有使用影响再说吧，现在本地合并然后推送远程仓库main”。替代暂停合并决定：授权本地提交、合并main、正常推送origin/main；不force、不tag/Release、不采购、不扩大部署。维护连接失败、真实异地备份、WSL长期恢复及M6-04仍未验收，原证据不改。当前已有8小时匿名窗口保持至23:37:08，不自动延长或重启。

只读确认/etc/wsl.conf systemd=true，systemctl docker enabled/active，Docker29.1.3；未执行WSL冷启动测试。以后现有电脑进入仓库执行./stockinsight.sh public即可自动恢复现有M6服务并启动8小时匿名入口，须保留终端/主机/网络。Docker启动尚未就绪时先稍候；确实未运行由用户执行sudo systemctl start docker。最终Git合并和远端结果以后续补记与实际Git为准。

## 首版合并最终记录（2026-10-12 16:16，Asia/Shanghai）

实际完成：5e5afb5（有限停牌采集/监控修复）、ad38557（限时匿名本机启动）已在feature分支提交。fetch核对远端main仍2cf6ff7后，本地main快进合并至ad38557，git push origin main成功；git ls-remote实测远端完整SHA ad38557ccfa1414387665e55466f27968df9b90c，与本地一致。工作区干净；本条交付记录另以docs提交同步main，不改功能代码。无force、tag、Release或额外部署。

合并前216个仓库文件及候选文件敏感扫描通过，无真实密码/私钥/运行数据入Git；Ruff/25文件格式/bash语法/git diff检查、文档链接围栏通过，运维22passed/0.08s。此前最终后端407passed与前端39/typecheck/build、原HTTPS11/公网19/手机反馈与补采验证仍有效，本轮合并未改业务代码、不重复执行采集或重启服务。保留原M6-04/维护失败/异地与长期恢复未验收状态，用户已接受且暂缓处理，不自动继续架构改造。

后续使用：当前WSL systemd=true，Docker enabled/active，进入现有仓库执行./stockinsight.sh public即可恢复现有服务并启动8小时匿名窗口，地址每次变化；当前已有窗口时不要重复启动，可status查看、public-stop提前关。主机/网络/终端需在线。WSL冷启动和断电恢复未做实测；Docker未就绪先稍候，确实未运行由用户sudo systemctl start docker。新电脑clone不含镜像/数据/私有配置，不能直接照此启动。

下一会话可复制：检查StockInsight main/origin/main同步状态和当前8小时窗口实际到期清理，不自动续期；根据用户实际使用反馈处理维护连接或数据问题。先读取AGENTS/规划/任务/交接/ADR及LOCAL_SERVER/修复记录，保护现有容器、数据、配置和部署的停牌修复，保持M6原失败证据，不自动采购、开放新服务或进入M7。

## 股票入门学习中心（2026-10-13，最新开发记录）

用户明确要求主页增加面向零基础的股票学习板块，覆盖概念、数据图表及交易知识。授权范围内新增六课、28项可搜索术语、6题纠错解释/重置、独立教学K线与读图练习；首页、导航和使用教程连接 `/learn`。原生SVG示例明确非真实行情，未接入行情API或数据库。学习完成不等于可以盈利；不推荐个股、不实现开户/下单/模拟账户，不提前实现财报或风险分析业务。

### 架构、数据库与部署

纯前端延迟加载扩展，无新依赖、API、Schema或migration；`0001_initial_schema`不变。本轮未连接数据库、重建原容器、使用私有凭据或重新开启公网。现有Caddy/匿名预览使用镜像内静态资源，新源码不会通过 `stockinsight.sh public` 自动发布。具体文件、来源和验收见 `docs/STOCK_LEARNING.md` 与 ADR-029。原M6-04、维护连接失败、异地备份与WSL恢复等限制保留。

### 实际测试

- Node22 `npm run typecheck`：通过。
- `npm test`：6个测试文件、44项通过（原39项+新增5项学习页交互测试）。
- `npm run build` / `npm run build-only`：通过；学习页chunk约22.26KB、gzip10.42KB，既有StockDetail约604KB警告保留。
- 修改文档的本地链接/围栏与 `git diff --check`：通过。
- 浏览器：隔离loopback5181与官方Chromium实测通过：首页行情离线仍可进课、六课锚点、K线切换、答错解释/纠错、词典、直接刷新、390px无横向溢出和键盘操作，无页面脚本异常。截图在 `/tmp/stockinsight-learning-*.png`。首次缺浏览器、完整下载超时、缺libnspr4/libnss3的失败记录保留；后续分段续传、完整大小/ZIP CRC校验及Ubuntu软件包临时解压后成功，未关闭TLS校验或安装系统包。
- 最初测试环境无中文字体，截图出现方框；文泉驿字体软件包仅解压到/tmp，使用独立Fontconfig后中文桌面/手机截图及全部交互再次通过。未修改系统字体安装或应用字体依赖。

### Git与下一会话

会话开始本地main与origin/main跟踪一致，HEAD `51a073c`；未live fetch远端。当前工作分支 `feature/stock-learning-center`，本轮本地提交信息为 `feat: add beginner stock learning center`（最终SHA以git log为准）。EDU-01已完成，未授权本次功能合并或push，不复用此前首版的单次push授权。无需购买服务器。下一步由所有者决定是否发布现有主机的静态资源并合并/同步GitHub；源代码完成与实际运行版本发布分别验收。隔离测试Vite在验收后关闭，不影响原容器。

下一会话可复制：

```text
继续StockInsight股票入门学习中心的发布准备。先按AGENTS阅读规划、任务、交接、ADR及docs/STOCK_LEARNING.md，检查feature/stock-learning-center实际Git状态、提交与测试记录。EDU-01源码及桌面/390px手机浏览器已验收。检查现有静态代理与匿名窗口，准备只更新前端资源的具体候选镜像、SPA /learn验收及回滚方案；只有在明确获准发布后更新目标服务，保护原API/数据库/scheduler/monitor及停牌配置。不自动合并、push、采购或续期开公网；如本轮用户已追加授权，以实际授权范围继续。
```

## 2026-10-13 学习页优化、实际发布及交付

用户明确要求更新前端、验证 `/learn`、检查优化并合并推送；本节替代上一节待授权发布说明。版本仍v0.1.0首版后教育扩展，EDU-01/02完成，M6-04仍未完整验收，不自动开展新业务里程碑。

- 在功能提交efbf3d1之上补充返回目录、清空词典搜索、六题完成提示，无依赖/API/数据库/采集变更，migration未执行且无需新增。
- 实际只重建生产proxy，镜像 `stockinsight-production-proxy:learn-20261013`（1d0f94adc483）；本机入口 `https://localhost:18443/learn`，原邀请密码与CA卷保留，私有env仅更新镜像标签。旧m6-validated镜像保留，回滚命令见docs/DEPLOYMENT.md，未实际执行回滚演练。
- API/DB/scheduler/monitor/backup容器ID和StartedAt对比均未改变。无运行中匿名代理，未开新公网窗口；下次主动 `./stockinsight.sh public` 使用新版镜像。本轮不声称已验证公网URL。
- 实际测试：Node22 `npm test` 44 passed；`npm run typecheck`、只读 `npm run build-only` 通过；隔离行情503和实际生产两种 `browser-learning.mjs` 模式通过，包含390px、键盘、刷新、锚点、测验、搜索；生产模式额外验证真实图表与只读设置，无页面脚本错误。先验证TLS链/主机名再固定浏览器证书公钥，不全局忽略TLS。11项服务门禁最终通过，首次重建立即探测ConnectionResetError保留，不承诺零中断。
- 学习页22.67KB/gzip10.56KB，既有详情604KB警告保留，后续按性能证据优化，不为警告增加依赖。本机无Buildx，使用现有legacy builder，未安装系统包。发现独立开发scheduler反复重启（生产scheduler正常running），本轮未诊断根因或更改开发服务。
- 原技术风险：M6维护连接失败、真实异地备份、WSL长期恢复和TLS监控等仍待后续，不改判；本次无新业务已知Bug。无需购买服务器。
- Git：开始工作区干净，fetch后main/origin/main均51a073c；完成实现与验证后按授权快进合并main并正常推送，实际结果在后续交付补记，不强推/删分支/tag/Release。

下一次可直接复制：

```text
继续StockInsight。先阅读AGENTS、PROJECT_PLAN、TASKS、SESSION_HANDOFF、docs/DECISIONS及docs/STOCK_LEARNING.md，核对main/远端和实际服务。学习页已部署，本轮先根据真实使用反馈复核/完善学习体验；若无具体反馈，先只读诊断stockinsight-local-scheduler反复重启，报告原因与建议，不自动重启或修复。保护生产API/数据库/停牌调度/监控，不自行续期开公网、采购或启动新业务里程碑；新改动的部署与Git推送按当轮授权执行。
```
