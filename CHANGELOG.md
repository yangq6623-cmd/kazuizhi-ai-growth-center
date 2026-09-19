# V2.1.0 R8 Final — 2026-09-19

- Completed R8-00 through R8-08 as one truthful growth-operations workflow.
- Added platform signal intake, deduplication, unique-account routing and durable growth IDs.
- Added the eight-agent content committee, owner review, RTX 3060 worker contract and quality gates.
- Added owner-gated publishing, verifiable platform receipts and unified conversations/leads.
- Added order attribution, 24h/72h/7-day metrics, content genes and learning feedback.
- Expanded one-phone-many-account bindings with role, region, service category and L1-L4 automation levels.
- Enforced cross-account stop-contact, platform/content matching and real local video paths.
- Added the R8 Final center, diagnostics, API coverage and full end-to-end regression tests.
- Reworked the installer to ZIP non-solid packaging and removed custom forced task termination to address Defender ML false positives seen in Preview #236.
- Added CI Defender scanning, security provenance, final handoff, user guide and live-configuration notes.

# V2.1.0 Beta R8 Preview R8-01B.4.3 — 2026-09-19

- Load the packaged WebView phone-mirror renderer directly before the dynamic R8 UI patches to eliminate startup-order stalls.
- Keep the runtime identity loader as a fallback and cache-bust the direct mirror script for upgraded installations.
- Add a regression contract covering the static bootstrap order, runtime fallback and PNG validation path.

# V2.0.0 Beta R7.1 — 2026-09-16

- Diagnosed the reported R6 screen as an older extracted executable still serving port 8876; the shown GitHub artifact was the separate V1.9.5 R3 build.
- Added persistent visible success/error feedback, missing-field focus and clearer content-generation guidance.
- Replaced internal action and metric keys in review and summary with user-facing Chinese labels.
- Verified navigation and the main actions across every page in an isolated browser session; preserved the R7 job engine and R3 baseline.

# V2.0.0 Beta R7 Core — 2026-09-16

- Added approval-gated persistent jobs for manual work, local daily review and system diagnostics.
- Added a local scheduler, interruption recovery, actual-step progress and a hash-linked audit trail.
- Registered eight AI employee roles as responsibilities; no background agent execution is implied.
- Added model-route visibility and an idempotent R6 user-data backup before R7 writes.
- Added a unified workflow page with approvals, progress, exceptions, roles and audit history.
- Preserved the R3 baseline and kept external publishing and financial actions outside the executor.

# V2.0.0 Beta R5 — 2026-09-16

- Restored AI task management, 7-day promotion calendar, competition analysis, customer demand analysis and the operations command center.
- Completed all 20 items in the original recovery plan.
- Redesigned navigation, dashboard, cards, forms, empty states, responsive layout and content results.
- Added keyword search, source filters, click-to-use, Chinese source labels, result copying and clearer validation messages.
- Changed the Windows runtime to windowed mode so normal startup no longer leaves a black console window open.
- Preserved review requirements, truth boundaries, persistent user data and the V1.9.5 Enterprise R3 baseline.

# V2.0.0 Beta R4 — 2026-09-16

- Restored the local keyword library, SEO content drafts, GEO local optimization, ad copy and short-video scripts.
- Added durable local storage for owner keywords and generated-draft history.
- Added read-only import of historical public keyword signals with explicit research-only labels.
- Added proposal-only enforcement, forbidden-claim rejection and no-auto-publish safeguards.
- Updated application, frontend, installer and Windows file metadata to `KZ-ENTERPRISE-V2-BETA-20260916-R4`.
- Preserved the V1.9.5 Enterprise R3 baseline and all existing V2 data and handoff documents.

# V2.0.0 Beta R3 — 2026-09-16

- Restored user growth, order conversion, technician supply, leader promotion and channel effect analysis.
- Added verified aggregate snapshot import with strict source/time validation.
- Added automatic read-only discovery for the established local business metrics bridge.
- Reject sensitive identity, address, secret and financial-detail fields from the analytics store.
- Feed verified business metrics into the daily operation summary while preserving explicit not-connected states.
- Updated application, frontend, installer and Windows file metadata to `KZ-ENTERPRISE-V2-BETA-20260916-R3`.
- Preserved the V1.9.5 Enterprise R3 baseline and all existing V2 review/history/AI Memory data.

# V2.0.0 Beta R2 — 2026-09-16

- Added a clear Chinese message when port 8876 is occupied, without a Python traceback.
- Stop the exact legacy R2/R3 runtime process during V2 installation so the new runtime can start.
- Replace stale V2 desktop shortcuts with a clearly named V2 Beta R2 shortcut.
- Updated application, frontend, installer and Windows file metadata to `KZ-ENTERPRISE-V2-BETA-20260916-R2`.
- Preserved the V1.9.5 Enterprise R3 baseline, installed files and handoff documents.

# V2.0.0 Beta Daily Review R1 — 2026-09-16

- Added the AI Daily Review Center, daily operation summary, problem analysis and growth opportunities.
- Added reviewable tomorrow plans, persistent review history and writable AI Memory.
- Added durable local data storage outside the installation directory.
- Added truthfulness, financial-action and persistence regression tests.
- Updated frontend build to `KZ-ENTERPRISE-V2-BETA-20260916-R1`.

# V2.0.0 Beta — 2026-09-15

Independent V2 source/spec/installer workflow; unified runtime and frontend identity; actual Setup artifact; automated install/reinstall/uninstall and R3 preservation checks. Historical AI feature recovery remains pending.

# CHANGELOG

## V1.9.5 Enterprise R3 — 2026-09-15

### 已完成
- 修复新安装包仍加载旧 Dashboard 的问题。
- Enterprise Dashboard 改为独立前端资源基线。
- PyInstaller spec 固定打包 Enterprise 前端资源到 `_internal/web`。
- GitHub Actions 增加打包前/打包后前端校验。
- 构建前清理 `build/`、`dist/`、`installer_output/`，避免旧产物污染。
- 修复 Inno Setup 已生成但 `build_installer.ps1` 误判失败的问题。
- Inno Setup 安装前强制清理旧 `_internal/web`。
- R3 使用独立 AppId、独立安装目录和独立快捷方式。
- R3 本地运行端口调整为 `8876`，与旧版 `8765` 隔离。
- 新版“卡嘴子 AI 增长运营中心 / 运营驾驶舱”已成功显示。
- GitHub Actions R3 Build #65 构建成功。

### 当前 Dashboard 已包含
- KPI 数据看板
- 业务数据趋势
- 增长分析中心
- SEO/GEO 中心
- AI 任务中心
- 自动化调度
- 系统健康/服务监控
- 今日任务/最新动态
- AI 运营建议
- 快捷操作

### 待处理
- 统一部分前端 `R2` 文案为 `R3`。
- 统一 Dashboard 端口显示为实际 R3 端口 `8876`。
- 清理左侧重复菜单项。
- 接真实订单、收入、用户、师傅、团长、SEO/GEO 等业务数据。
- 正式发布前评估隐藏 console 窗口并保留日志能力。

### 交接
详见：`docs/V1.9.5_ENTERPRISE_R3_HANDOFF_20260915.md`

---

## V1.9.5

新增：
- AI经营驾驶舱规划
- 月度经营报告体系
- 双增长分析模型
- 数据结构规划
- 版本管理体系

基于：V1.8.5
# V2.0.0 Beta R6

- Added an AI operations command center with four transparent AI roles and a seven-step review loop.
- Added honest integration status for local intelligence, external AI, business data, cloud sources, publishing and financial actions.
- Added an OpenAI-compatible connection test, Windows user-encrypted API credentials and a proposal-only AI operations assistant.
- Added one-click system diagnostics and clearer human-facing status, error and responsive-layout behavior.
