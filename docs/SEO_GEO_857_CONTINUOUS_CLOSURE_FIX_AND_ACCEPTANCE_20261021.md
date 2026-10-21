# 卡嘴子 #857 连续运行闭环修复与验收记录

日期：2026-10-21

范围：#856 现场只读取证、#857 最小增量修复、隔离回归和 Windows 候选构建门禁
安全边界：未创建 Mission/Command，未修改生产订单、资金、用户、小程序或现场持久账本；未发送外部 AI 问题，未发布网页，未提交旧 URL，未重试历史任务。

## 1. 准确基线

- 本机工作台可见版本：`#856`，Commit `0e5d8273`。
- 完整安装提交：`0e5d827358608a6887527f692435fa40fa2fc3e4`。
- 该合并提交 tree：`de3c6699b9931d5036102df0edd6319c3907e7d1`。
- PR #31 参考提交 `c85b5ad5890db512aac2c4a6072273711adecd0e` 的 tree 同为 `de3c6699b9931d5036102df0edd6319c3907e7d1`，因此本修复以 `c85b5ad` 的完全相同源码内容建立分支，而不是以旧 main 重打包。
- #856 Windows 构建：GitHub Actions Run `39526364914`，成功。
- 本轮没有通过容器终端直接读取用户 Windows 文件系统中的 BUILD_RECORD；版本身份以工作台可见 Commit、Git tree 等价性和 #856 Actions 产物来源交叉验证。该限制不包装成“已直接读取安装目录”。

## 2. #856 现场真实数据（重新读取，不沿用旧快照）

取证窗口：2026-10-21 22:59—23:14（+08:00）。

| 范围 | 真实结果 | 结论 |
|---|---:|---|
| Mission | 1131/1132，queued 1，running 0，failed 0 | 来自完整任务账本，不再受最近 200 条列表窗口影响 |
| 当前工作台批次 | `R7-20261021-B01` | 与已经执行过的续轮任务不一致，确认是批次身份回退显示缺陷 |
| 下一次资格唤醒 | 2026-10-22 12:35:22 +08:00 | 未强制完成剩余 queued 任务，未强造 B02/B03 |
| SEO 累计 | Asset/公网 32，搜索提交 31 | 今日新增独立 URL 0，今日新增提交 0 |
| SEO 今日 | 页面显示生成 8、QC 0、公网 0、提交 0 | 8 条实际为既有 Asset 修订，不是 8 个新 Asset |
| GEO 正式基线 | 50/50，Evidence 50 | 固定基线完成不等于持续复测增长 |
| GEO 效果 | 提及 5，主动推荐 0，官网引用 0 | 严格按正式 Evidence 口径 |
| GEO 运营复测 | 24h 5/13、72h 2/13、7d 0/13 | 不提前补造复测 |
| GEO 队列 | 3 条；浏览器代理 5/5 就绪 | UI 报“可领取”，匹配平台 Claim 却返回 `queue_empty`，口径矛盾 |
| 历史待核查 | 78；其中技术超时 73、未分类 5；不确定发送 78（可重叠） | 全部保留，未重试 |
| C 级 Signal | 888 | 不等同正式 Evidence，也不等同豆包计费 API 调用量 |
| GSC | 28 天窗口 2026-09-24—2026-10-19；0 点击、0 展示；页面显示约 4 小时前更新 | 有数据延迟，不能推导 10 月 21 日实时结果 |
| 经营结果 | 官网落地事件 11、打开小程序事件 30、微信 UV 1、咨询 0、今日订单 0、历史完成订单 2 | 历史订单未归因给本轮 SEO/GEO；不同埋点事件不能称为“200%点击率” |

工作台最新可见 GEO 调度为 22:59:30，360 平台 Claim 为 23:02:16，Mission 阶段回执持续至 23:09。说明总调度和阶段心跳仍运行，但不证明外部任务已成功执行。

## 3. 六项问题的证据、根因和处理

### 3.1 GEO 三条正式任务

| Task ID | 严格路由 | #856 现场状态 | #857 处理 |
|---|---|---|---|
| `GEO-TASK-95EE62BA113C` | `deepseek_web/browser/deepseek_web` | queued；UI 称可领取，真实 Claim 与安全门禁结果不透明 | Claim 与诊断统一调用同一门禁，返回具体 `claim_blocker` |
| `GEO-TASK-FEF4F799B1B1` | `so360_ai_search/browser/so360_ai_search` | queued；匹配 360 Claim 返回 `queue_empty` | 被历史尝试、退避或不确定结果阻断时改报 `queue_blocked` 和 Task ID/原因 |
| `GEO-TASK-6EBC1B10DD82` | `deepseek_web/browser/deepseek_web` | queued；同上 | 同上 |

根因：#856 的 `_queue_diagnostics()` 只检查 provider/method/platform，因此把任务标为 `claimable_by_matching_browser`；原子 Claim 另行应用 `fresh_only`、历史 attempt、发送不确定和退避门禁，最终无任务时统一返回 `queue_empty`。两条路径语义不一致。

修复后：

- `retry_backoff`
- `uncertain_external_result_requires_reconciliation`
- `prior_external_attempt_requires_reconciliation`
- `retry_approval_missing`
- `strict_route_mismatch`

都会显示为可追溯阻塞；只有全新且路由一致的任务，或带精确总控批准记录的安全 retry 才可领取。#857 没有替三条现场任务猜测或改写 attempt；安装后由新增字段读取每条真实 blocker。

本轮新增真实 GEO Evidence：`0`。原因是遵守“不确定发送不得重复”的安全边界，未通过浏览器发送任何问题。DeepSeek 和 360 页面会话可读、扩展 5/5 就绪仅证明会话/连接存在，不作为执行成功。

### 3.2 SEO Asset 到公网与提交

确认的既有 Asset 修订回执包括：

- `SEO-95949E42D94F` → `/seo/93479fcc67a7d885/` → `REMOTE-DEPLOY-SEO-95949E42D94F-20261021T152613+0800`
- `SEO-EB5CA7B78D1B` → `/seo/eacb67cad803e796/` → `REMOTE-DEPLOY-SEO-EB5CA7B78D1B-20261021T150844+0800`
- `SEO-39333FE29CE0` → `/seo/919cb9dba488b334/` → `REMOTE-DEPLOY-SEO-39333FE29CE0-20261021T141128+0800`
- `SEO-0A6FBE492759` → `/seo/0d3e2fe0ff24f0d5/` → `REMOTE-DEPLOY-SEO-0A6FBE492759-20261021T133451+0800`
- `SEO-BC1C67E6D559` → `/seo/79a2fbad601aaa64/` → `REMOTE-DEPLOY-SEO-BC1C67E6D559-20261021T131529+0800`
- `SEO-BDBB6D3893E0` → `/seo/bc999910286a647c/` → `REMOTE-DEPLOY-SEO-BDBB6D3893E0-20261021T131531+0800`
- `SEO-2C849DBFF9E1` → `/seo/22e0e824e08a0225/` → `REMOTE-DEPLOY-SEO-2C849DBFF9E1-20261021T130841+0800`

面板汇总为 8 条既有页面修订；浏览器输出截断前取得 7 条完整映射，第 8 条 ID 未在本轮证据中完整取出，保留为验收缺口，不推测补写。

根因：`refresh_legacy_staging()` 对既有 Asset 重建页面时覆盖 `generated_at`，导致旧 Asset 修订被今日“新生成”统计命中。

修复后：保留首次 `generated_at`，新增 `last_staging_refresh_at` 和 Revision ID；面板拆成“新 Asset 生成”和“旧 Asset 修订”。历史 stage、URL、发布 Receipt、搜索提交 Receipt 均保留。今日真实新增 Asset、新 URL、新提交均为 `0`。

### 3.3 Mission 续轮

根因：续轮函数在“无新资格”时未返回最近真实 batch 元数据，调用方回退为 B01。已有任务/回执能证明续轮资格检查继续发生，但页面把健康等待误显示成仍在 B01。

修复后：B02/B03 在完成后仍保留自己的 `batch_id`、`batch_number`，状态显示 `completed_waiting_eligibility`；有新合格资格才创建下一批，不创建新 Mission，不重复 fingerprint。

现场最后 1 条 queued 任务的 Task ID/due/source 未被 #856 页面/API完整暴露；未将它强制完成。下一次已知资格唤醒时间为 2026-10-22 12:35:22 +08:00。

### 3.4 统计口径

- 30/30、27/28：页面/阶段局部计划口径。
- 1131/1132：当前 Mission 完整账本。
- 32/31：SEO 累计公网 URL/带搜索平台回执的提交。
- GEO 运营发布 8：既有 URL 的内容 Revision/重新发布回执，不是 8 个新增 URL。
- GEO 50/50：固定正式 A/B 基线完成度，不是今日任务完成率。
- 100% 必须带上“本地任务完成率”范围，不得当作对外业务闭环完成率。

#857 为数据卡增加新/旧 Asset 区分，候选稳定性明确标注“历史进程累计，不是当前 Build 独立 24 小时验收”；官网落地与打开小程序改称“事件比”，不再称点击率/转化率。

### 3.5 稳定性与积压

#856 页面累计连续记录为 342.48 小时、2235 周期、2129 成功、106 异常、11 次真实进展。源码表明这是从首个周期开始的历史进程累计，没有 Build/candidate 维度，因此不能作为 #856 独立 24 小时 99.5% 可用率证明。

结论：#856 独立连续 24 小时验收 **未通过（证据范围不足）**。旧 `run-785-5201523` 不移用于 #856。#857 安装后必须新开自然时间窗口；CI 或模拟测试不能替代 24 小时和 7 天实际经过。

内容中心 118 条历史待处理/待确认/失败数据未清空。本轮没有自动恢复状态不确定的对外动作。

### 3.6 技术 SEO 和经营真实性

最近公网审计仍报告 7 项：主页结构化数据、canonical、Open Graph、可抓取正文、普通内链，根 sitemap 类型，子 sitemap `lastmod`。源码生成器已经为 SEO 子页输出 canonical/schema，并为子 sitemap 输出 `lastmod`；问题集中在生产首页/root sitemap 或部署版本差异。本轮未获生产服务器写入授权，因此不改生产站。

公网抽检 20/20 可访问，中位响应约 154 ms，慢于 3 秒为 0。该结果不证明 Google 已抓取/收录。

## 4. 实际修改文件

- `core/daily_workforce.py`：保留最近真实 Batch 身份和等待状态。
- `core/r8_22_autonomous_convergence.py`、`web/r8_22_autonomy.js`：透传并解释批次等待状态。
- `core/geo_validation.py`、`integrations/geo_browser_agent.py`：统一 GEO 诊断/Claim 安全门禁，持久化 retry 批准来源，返回准确阻塞。
- `core/seo_geo_growth.py`、`backend/r8_13_seo_geo_patch.py`、`web/r8_13_seo_geo.html`：新 Asset/旧 Revision 分账，保留原始时间和回执，修正经营事件比和候选稳定性文案。
- `core/seo_geo_autonomy.py`：明确历史进程累计不具备候选独立验收资格。
- `test_857_continuous_closure_acceptance.py`：新增定向回归。
- `test_geo_808_browser_claim_truth.py`：旧 `queue_empty` 契约升级为可审计 `queue_blocked`，不放宽 no-replay。
- Windows workflow：增加 #857 隔离门禁和候选报告打包。

## 5. 测试结果

- #857 定向：通过。
- #854 全账本/续轮/严格路由/QC：通过。
- #841 SEO 质量与调度隔离：通过。
- #824 字段真实性：通过。
- GEO 808/812/浏览器代理兼容：通过。
- R8-13/R8-14/R8-22、daily workforce：通过。
- Python `compileall`、全部 Web/扩展 JavaScript `node --check`、`git diff --check`：通过。
- Windows 主构建 workflow 中 82 个唯一测试命令：本机可运行的 80 个全部通过；2 个 Selenium 冷启动测试因当前 Linux 容器未安装 Selenium 未本地执行，必须由 Windows CI 的 pinned requirements 环境执行。

历史独立 workflow 的已知失败不能写成全绿：R8-10/R8-11/R8-12/R8-15/R8-19 中仍有测试断言已退役的 ADB、旧 GEO 直达页、旧 `phase: R8-15` 或旧连接器队列状态。这些失败可在未改业务代码的 #856 基线复现，属于过时测试契约；主 Windows 发布门禁使用当前 R7/R8 契约。本 PR 不借机大范围改写历史 workflow。

## 6. 候选构建、安装和回滚门禁

候选仅在以下 GitHub Actions 步骤全部成功后交付：源码回归、#857 测试、打包运行时、Defender 检查、静默安装、启动、覆盖升级、持久数据保留、卸载。Commit、Run、SHA256 和 BUILD_RECORD 由 CI 产物记录，不能在构建前预填假值。

覆盖升级前备份 `%LOCALAPPDATA%\KazuizhiAI`。安装包不得删除或初始化该目录；回滚使用已保存的 #856 安装包覆盖安装并保留同一数据目录。禁止通过删除队列/账本解决兼容问题。

## 7. 最终真实产出与未完成事项

本轮诊断/修复期间：新 Asset `0`，新 URL `0`，新搜索提交 `0`，新正式 GEO Evidence `0`，GSC 已报告点击 `0`、展示 `0`，新咨询 `0`，今日订单 `0`。没有把本地任务、Revision、C Signal、SUBMITTED 或历史订单包装成增长。

未完成：

1. 三条现场 GEO 任务的各自 blocker 需在 #857 安装后从新增诊断字段读取；本轮不重复发送。
2. 第 8 条既有 Asset 修订的完整 ID 映射未从截断的 #856 页面输出取得。
3. #856 独立 24 小时 99.5% 证据不存在；#857 的 24 小时/7 天必须自然经过。
4. Google 10 月 20—21 日的抓取、收录、曝光仍受 GSC 延迟影响。
5. 7 项生产技术 SEO 需在获得服务器变更授权并核对部署版本后处理。
6. 用户本机 #857 真机覆盖安装验收只有在用户安装候选后才能成立；Windows CI 不冒充本机验收。
