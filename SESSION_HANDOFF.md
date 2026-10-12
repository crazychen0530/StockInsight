# StockInsight 会话交接

更新时间：2026-10-12，Asia/Shanghai。当前工作目录 `/home/crazychen/myprojects/StockInsight`。

> 当前状态以第12节为准：M6-01需求与容量评估完成，首期2–10名受邀用户/约100股。当前分支feature/m6-capacity-assessment，基于f67b011（包含尚未合并main的两轮页面/来源功能）；M6-02～04未实施，无采购/公网部署/合并/push授权。下文M6未启动的描述是历史时点。

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
