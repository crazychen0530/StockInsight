# StockInsight 会话交接

更新时间：2026-10-12，Asia/Shanghai。当前工作目录 `/home/crazychen/myprojects/StockInsight`。

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

**M5-01～05 全部 DONE，v0.1.0 RC 准备完成。**分支 `feature/m5-live-data-acceptance`，最终提交见Git日志；不合并main、不推送、不创建tag/Release。本轮在M5发布候选验收完成后停止，后续合并/同步或进入M6需用户明确指示；远程main已只读核验仍为aa3da561d7054adacf93c01fdff4f9fd5af09ca9。

下一会话可复制任务（仅在用户明确要求公网后）：

```text
继续 /home/crazychen/myprojects/StockInsight，执行 M6-01 部署需求与容量评估。先依次阅读 AGENTS.md、PROJECT_PLAN.md、TASKS.md、SESSION_HANDOFF.md、docs/DECISIONS.md、docs/M5_ACCEPTANCE.md，检查实际Git/服务状态。M5已全部验收，本地4只股票真实数据与scheduler正在运行；保护原库/卷及加密备份。先依据实际数据量、预期访问规模、HTTPS/认证/最小权限/数据公开授权条件形成具体方案，不擅自采购、公开部署、发布Release或清库；合并/推送只按用户的新明确授权执行。
```

验收证据副本在data/acceptance/m5-20261012/（Git忽略）；临时恢复实例已停止但卷保留，原开发db/API/web/scheduler继续运行。
