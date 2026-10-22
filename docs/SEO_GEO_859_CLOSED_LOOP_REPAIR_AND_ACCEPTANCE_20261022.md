# 卡嘴子 #859 SEO/GEO 闭环集中修复与验收记录

日期：2026-10-22

基线：本机安装身份由用户现场提供为 Build #859；源码精确基线为合并提交
`23ae0e51281cb4f6237185eb3e1d21867faaff74`。该提交已直接获取并以独立分支
`codex/859-closure-reconciliation` 建立工作树，未覆盖运行中的 #859。

安全边界：没有新建 Mission/Command，没有访问订单、资金、用户或正式小程序，
没有清空 GEO 队列/Evidence，没有外发 AI 问题、重试历史任务、发布生产网页或提交旧 URL。

## 1. 证据范围

- 用户现场参考快照（2026-10-22 约 12:20，+08:00）：Mission 1141/1152、等待 11、
  B01 10/20；SEO 公网 32、提交 31；GEO 50/50、提及 6、推荐 0、引用 0、正式队列 3、
  历史待核查 78、C 级 Signal 888。
- 精确源码：Commit `23ae0e5`，不是旧 main，也未假设 PR #32 的某个中间提交等于安装版。
- 本次执行环境没有用户 Windows 文件系统或终端。本机 `127.0.0.1:8876` 通过云端浏览器读取被
  安全策略拒绝，以防私有账本被带出本机；因此上述现场数值没有被冒充为本轮最新快照。
- 新增 `Export-Kazuizhi859Diagnostics.ps1` 只用 GET 读取本机接口，自动屏蔽密码、Token、Cookie、
  Secret、Authorization 和原始回答正文，并为导出文件生成 SHA256。脚本不领取、不重试、不发布、不改配置。

## 2. 已确认根因与最小修复

| 项目 | 原始根因 | 修复 | 外部副作用 |
|---|---|---|---|
| SEO 新 Asset 停止 | `plan_today()` 只消费持久账本中未绑定 Asset 的 Opportunity。基线 Opportunity 全部绑定后，函数永久返回 0；当天已启动时自治循环只生成现有 PLANNED Asset，不发现下一条去重机会 | 增加有界的已验证服务意图池；只有“所有 Opportunity 已绑定”时，每个自然日最多新增 1 条未覆盖的涟水县高意向 Opportunity。仍由原 PLANNED→GENERATED→QC→发布→提交链处理 | 自动发现/本地生成不等于发布；没有逐 Asset 发布授权或连接器时停在可追溯阶段 |
| GEO 三条旧任务 | #859 的 no-replay 门禁能识别 prior attempt，但旧 `legacy_receipt_reconciliation()` 只查看 `authorization_required`，无法核对三条 `queued + prior attempt` 任务 | 新增按明确 Task ID 的只读核对和显式应用接口。只有 Task、Question、Provider、Run、Attempt 和 Evidence 唯一匹配现有真实 Receipt 时才修正本地状态；否则继续冻结 | 新外部请求 0，新 Evidence 0；应用前自动备份 queue；歧义/缺失证据绝不转为成功 |
| B01/B02/B03 | #857 已修复批次身份回退。12:20 的 B01 10/20 属于当日时间排班尚未终态，不能强制创建 B02 | 保留原机制。B01 全部合法终态后，只有待推进 Asset 或已到期 GEO Schedule 才创建 B02；同一资格指纹只建一次，新 Revision/新到期资格可创建 B03；无资格显示等待 | 不新建 Mission，不生成凑数任务，不强制完成未来任务 |

## 3. 三条 GEO Task 的现场处置状态

| Task ID | 已知路由 | #859 参考状态 | 本轮可下结论 |
|---|---|---|---|
| `GEO-TASK-95EE62BA113C` | DeepSeek/browser/deepseek_web | `blocked_by_safety_gate`，已有尝试 | 禁止重发；需本机精确 Task/Run/Attempt 与 Receipt 唯一匹配结果 |
| `GEO-TASK-FEF4F799B1B1` | 360/browser/so360_ai_search | `blocked_by_safety_gate`，已有尝试 | 禁止重发；需本机精确 Task/Run/Attempt 与 Receipt 唯一匹配结果 |
| `GEO-TASK-6EBC1B10DD82` | DeepSeek/browser/deepseek_web | `blocked_by_safety_gate`，已有尝试 | 禁止重发；需本机精确 Task/Run/Attempt 与 Receipt 唯一匹配结果 |

尚未把任何一条写成 succeeded。缺失的唯一证据是用户 Windows 持久账本中的 Attempt/Run 与原始 Receipt/Evidence；
仓库不含这三条生产记录。安装候选后，GET
`/api/r8-19/geo/task-reconciliation?task_id=<ID1,ID2,ID3>` 会返回逐条持久字段和以下处置之一：

- `unique_authoritative_receipt`：可以只关联旧回执，不发送新问题；
- `prior_attempt_without_matching_receipt_hold`：继续隔离；
- `ambiguous_multiple_receipts_hold`：继续隔离；
- `uncertain_external_result_hold`：继续隔离；
- `safe_never_attempted_no_receipt_to_reconcile`：只说明从未尝试，仍须经过正常资格/冷却/路由领取。

## 4. 隔离端到端验收

定向测试 `test_859_closed_loop_repair.py` 使用临时 `LOCALAPPDATA` 和 HTTP 测试替身，完成：

1. 将全部基线 Opportunity 标为已绑定；
2. 自动选择未覆盖的 `涟水县空调不制冷上门维修`；
3. 生成新 Opportunity ID 和新 Asset ID；
4. 进入 GENERATED，严格 QC 通过；
5. 通过原部署 Worker 产生隔离公网部署 Receipt；
6. 通过原 IndexNow Worker 产生隔离提交 Receipt并进入 SUBMITTED；
7. 同日重复规划不产生第二条；
8. 三条模拟 GEO 旧任务中只修正唯一匹配 Receipt 的一条，另外两条保持 queued；
9. B01 完成后产生 B02；同一资格不重复；Revision 改变后产生 B03。

该测试证明代码闭环和 no-replay 约束，不等于生产新增 URL、搜索平台真实接收或真实外部 AI Evidence。

## 5. 回归结果

已通过：#859 定向、#857、#854、#840、#836、R8-14、R8-15、R8-16、GEO 808、daily workforce，
以及 Python 编译和 `git diff --check`。主发布工作流去重后的 Python 命令在 Linux 隔离环境执行 75 项，
其中 73 项通过；仅 `test_geo_774_async_boot_browser.py` 和 `test_r8_25_owner_cold_start.py` 因 Linux
环境未安装 Selenium 而未执行。8 项 Node 回归全部通过。上述两项必须由安装了 pinned requirements 的
Windows CI 执行。静默安装、覆盖升级、持久数据保留、Defender 和卸载结果以 GitHub Actions 实际 Run
为准，不能在 Run 完成前预填。

## 6. 技术 SEO、稳定性和经营真实性

- 7 项生产技术 SEO 问题本轮没有直接写生产站。源码已为子 sitemap 生成 `lastmod`，新 SEO 页面已输出
  canonical、Open Graph、Schema、可抓取正文和普通链接；生产首页/root sitemap 是否仍旧必须以实时公网审计确认。
- #859 的 24 小时和 7 天自然时间验收尚未完成；CI、历史版本在线率或模拟时钟不能替代。
- 118 条历史内容积压、11 项账号/授权提示没有清空或自动绕过。缺少本机账本证据时不判断其为陈旧提示。
- 本轮真实新增业务成果：生产新 Asset 0、新 URL 0、新搜索提交 0、确认收录 0、曝光 0、点击 0、
  新正式 GEO Evidence 0、推荐 0、引用 0、咨询 0、订单 0。

## 7. 覆盖安装与回滚

覆盖升级前备份 `%LOCALAPPDATA%\Kazuizhi_AI_Enterprise_V2.0.0_Beta\data`。安装器不得删除或初始化该目录。
回滚使用保留的 #859 安装包覆盖安装，继续使用同一数据目录。针对 GEO 的显式 Receipt 关联会先在
`data\geo_validation\backups\` 写入 queue 快照；它不删除 Receipt/Evidence 或 Attempt。

## 8. 尚未通过

1. 三条生产 GEO Task 的逐条最终处置：等待候选安装后读取本机新诊断接口；当前不得重发。
2. 生产新 Asset 的真实发布/提交：本轮没有操作生产官网；需候选安装后同时满足 QC、逐 Asset 授权、部署连接器和真实 HTTP/搜索回执。
3. Google 抓取、收录、曝光与点击：受 GSC 数据处理窗口影响，不能由 SUBMITTED 推断。
4. #859/#下一候选 24 小时和 7 天自然运行：时间尚未实际经过。
5. 本机安装验收：Windows CI 不能代替用户机器安装后的现场复检。
