# 卡嘴子 #872 现场差异核验、定向修复与候选验收

- 日期：2026-10-23
- 现场版本：R8-24 · #872 / `e4238e93`
- 精确源码基线：`e4238e937c3e01d83f4ac55c2b6bb547a9e8a4eb`
- 修复分支：`codex/872-field-consistency-fix`
- GitHub 候选提交：`3a030cd1446aac8275f1eb57d363b396e17c35ab`
- Pull Request：[#36](https://github.com/yangq6623-cmd/kazuizhi-ai-growth-center/pull/36)
- 生产安全边界：未创建 Mission/Command，未重试 GEO 历史任务，未发送外部 AI 问题，未发布社媒，未修改订单、资金、用户、小程序或生产数据库。

## 1. 现场基线与统计口径

Chrome 现场只读复核得到：Mission 1178/1185、运行 0、等待 7；SEO 公网页面 35、搜索提交 34；正式 GEO Evidence 50/50、品牌提及 8、主动推荐 0、官网引用 0；GEO 正式队列 4、历史待核查/待授权 78。

R7 当日 18/25 与 19/25 是不同刷新时点的快照；AI 决策页在 15:00:09 显示 19/25。Mission 1178/1185 是 Mission 全账本，不能与当日排班或外部发布相加。该差异不是新代码故障。

SEO “今日 Asset 首次公开”与 GEO “机会发布事件 URL（去重）”是不同集合：前者按 Asset 首次 PUBLISHED 计数，后者按 GEO Opportunity 的发布事件 URL 去重。已在 UI 与 API 中增加明确 scope，不再用相同“今日发布”标签混淆。

## 2. 确认并修复的新缺陷

### 2.1 GEO 唯一历史 Receipt 没有进入真实领取路径

既有 #859 代码已经实现 Task/Question/Provider/Run/Attempt 精准对账，但 Chrome 执行器的 `claim_next_task()` 只检查防重放门禁，并不会调用对账器。因此，即使某个 Task 只有一条唯一权威 Receipt，也会持续显示 `prior_external_attempt_requires_reconciliation`，除非人工调用对账接口。

修复：

- 真实、严格平台、fresh-only 浏览器执行器领取前，先只读筛选同平台的历史尝试阻塞任务。
- 仅在恰好一条权威 Receipt 精确匹配时恢复本地关联和终态。
- 零条或多条匹配继续隔离；不创建 Evidence、不发送外部请求、不增加 Attempt。
- 队列详情增加 Run ID、Attempt ID、匹配 Receipt 数、对账处置状态。
- 无 `task_id` 的只读对账 GET 返回稳定的 `task_id_required` 响应，不再断开连接。

涉及现场任务：

| Task ID | #872 现场状态 | 候选逻辑 |
|---|---|---|
| GEO-TASK-95EE62BA113C | blocked_by_safety_gate | 唯一 Receipt 才本地关联；否则隔离 |
| GEO-TASK-FEF4F799B1B1 | blocked_by_safety_gate | 唯一 Receipt 才本地关联；否则隔离 |
| GEO-TASK-6EBC1B10DD82 | blocked_by_safety_gate | 唯一 Receipt 才本地关联；否则隔离 |
| GEO-TASK-80424A49BBD6 | blocked_by_safety_gate | 唯一 Receipt 才本地关联；否则隔离 |

安装 #872 现场未被改写，因此四条当前仍保持安全隔离。候选安装后会输出每条的可审计 disposition；没有唯一证据的任务不会被强行完成或重发。

### 2.2 已发布 SEO Asset 的服务语义退化

5 个 GEO 关联公网 URL 均实测 HTTP 200，canonical 均指向自身，说明 URL/Canonical 映射没有故障。但其中 4 个 Asset 的本地记录已退化为 `region=""`、`service=""`、`keyword=<slug>`，公网标题也退化成“涟水县本地服务需求发布与办理指南”。

| Asset ID | 公网 URL | 现场标题结果 | 原发布 Receipt |
|---|---|---|---|
| SEO-39333FE29CE0 | https://kazuizhi.com/seo/919cb9dba488b334/ | 正常：涟水县管道疏通本地服务 | REMOTE-DEPLOY-SEO-39333FE29CE0-20261023T143012+0800 |
| SEO-BC1C67E6D559 | https://kazuizhi.com/seo/79a2fbad601aaa64/ | 退化为通用本地服务 | REMOTE-DEPLOY-SEO-BC1C67E6D559-20261023T133758+0800 |
| SEO-BDBB6D3893E0 | https://kazuizhi.com/seo/bc999910286a647c/ | 退化为通用本地服务 | REMOTE-DEPLOY-SEO-BDBB6D3893E0-20261023T133802+0800 |
| SEO-2C849DBFF9E1 | https://kazuizhi.com/seo/22e0e824e08a0225/ | 退化为通用本地服务 | REMOTE-DEPLOY-SEO-2C849DBFF9E1-20261023T132858+0800 |
| SEO-E3653895409B | https://kazuizhi.com/seo/6e1e1d73c62a160d/ | 退化为通用本地服务 | REMOTE-DEPLOY-SEO-E3653895409B-20261023T132054+0800 |

根因是发布回执恢复逻辑允许在缺少 Opportunity 语义时建立最小 PUBLISHED Asset；后续模板刷新把 slug 当作关键词，并用默认“本地服务”重建页面。原始字段为何先从 SEO 主账本缺失，仅凭当前账本不能唯一证明是进程中断还是并发旧写覆盖；但“最小恢复记录可被再次发布成通用内容”这一持续故障点已经由现场数据和源码共同确认。

修复：

- 从 deploy Receipt asset snapshot、GEO growth asset/revision、SEO Opportunity 三类来源中按优先级恢复。
- 必须满足 `_stable_id("SEO", region, service, keyword) == Asset ID` 才接受；禁止按 URL 或相似文本猜测。
- 保留原 URL、PUBLISHED/SUBMITTED 状态、首次发布时间及所有提交 Receipt。
- 为修复后的内容生成独立 `SEO-META-*` Revision；只有新版本取得新的公网部署 Receipt 后才清除 repair pending。
- 所有后续本地/Remote Agent/直文件发布 Receipt 增加脱敏 `asset_snapshot`，仅含公开身份字段，不含 Token、密码、Cookie、路径凭据。

隔离回归使用现场同一 Asset `SEO-BDBB6D3893E0` 复现：修复前关键词为 slug，修复后恢复为“涟水县家电维修本地服务”，原 SUBMITTED 状态、URL 和搜索提交 Receipt 均未变化。

## 3. 已确认正常或不是本轮新缺陷

| 项目 | 结论 |
|---|---|
| Mission/R7 当日数字差异 | 刷新时点与统计范围不同；不是容量上限或调度停止 |
| SEO 35 / 搜索提交 34 | 累计真实账本；SUBMITTED 不代表 INDEXED |
| GEO 50/50 | 固定正式 A/B 基线，保持不增长是正常口径 |
| GEO Signal 903 | C 级运营 Signal，不等于正式 Evidence、付费 API 次数或推荐成果 |
| 历史 78 条待核查 | 继续保留，禁止批量重试或清零 |
| 社媒已验证发布 0 | 执行中心仍有 24 个账号/授权事项；草稿与路由登记不能冒充 Post ID/URL |
| 经营数据 | 只读连接正常；落地信号 11、小程序打开信号 30、WX UV 0、咨询 0、当日订单 0；收入归因字段仍不支持 |

## 4. 官网技术 SEO 实时复核

2026-10-23 公网复核：主页、robots、根 sitemap 均 HTTP 200。当前结果：

- 首页仍缺 Schema、canonical、Open Graph、可抓取正文、普通内部链接。
- 根 `sitemap.xml` 仍是仅含首页与子 sitemap 的 `urlset`，应为 `sitemapindex`。
- `robots.txt` 已包含 sitemap 声明，正常。
- `/seo/sitemap.xml` 为 `text/xml`，子页面具有 `lastmod`，该历史问题已恢复。
- 新 SEO 内容页自身具备 canonical、Schema、正文和小程序入口。

首页与根 sitemap 属于既有生产站文件/部署权限问题，不是本轮新增客户端回归。当前未获得覆盖生产根站文件的明确授权，因此未修改。

## 5. 测试结果

通过：

- `test_872_geo_reconciliation_claim_closure.py`
- `test_872_seo_metadata_recovery.py`
- `test_r8_13_seo_geo_growth.py`
- `test_geo_808_browser_claim_truth.py`
- `test_841_seo_content_quality.py`
- `test_841_scheduler_isolation.py`
- `test_854_closed_loop_concentration.py`
- `test_857_continuous_closure_acceptance.py`
- `test_859_closed_loop_repair.py`
- `test_860_seo_publication_closure.py`
- `test_862_control_bus_r7_read_reliability.py`（1205 条账本并发读取）
- `test_r8_15_seo_public_deploy.py`
- `test_r8_17_remote_agent.py`
- `verify_v2_autonomous.py --source`
- Python compileall、Node syntax、`git diff --check`

所有新增回归均使用临时 LOCALAPPDATA/HTTP double；未触发生产发布、搜索提交或外部 AI 发送。

## 6. GitHub 与 Windows 候选交付

- Windows CI：Build #874 / Run `39952624510`，结论 `success`。
- Actions：https://github.com/yangq6623-cmd/kazuizhi-ai-growth-center/actions/runs/39952624510
- Artifact ID：`12500924281`，Artifact ZIP SHA256：`f918245326f8190b898f72bb9e8d5e24c769130dfaccfe39246df34595063b75`。
- 安装器 SHA256：`6B8E3FB5EDF8D53EACCF22D3E4600A71E1FAF091FCE3B727DE251D017941AFD1`。
- Chrome GEO 扩展 SHA256：`73B68E7565F439BEE5B0C6F9761B29D8CDF9905E2406920D1A0A8AA0D7382D89`。
- Defender：0 detection，扫描通过。
- Authenticode：`NotSigned`；CI 中 Azure Artifact Signing 未启用，因此不得描述为已签名安装器。
- Windows 门禁：静默安装、启动、覆盖升级、持久数据保留、卸载均通过。
- 包内 BUILD_RECORD 已明确列出 #872 三项检查，并明确排除生产 GEO 对账、生产 SEO 修订再发布、社媒回执、索引/转化和自然 24h/7d 的虚假声明。

## 7. 仍未通过的现场验收

1. 当前运行的是原 #872，尚未安装本候选；四条 GEO 任务和四条通用 SEO 页面仍未在用户机上完成候选后的真实复核。
2. 真实社媒 Post ID/URL 仍为 0，需对应平台登录/授权；这不是安装包可以绕过的条件。
3. Google 抓取、收录、展示、点击尚无新证据；搜索提交不能替代收录。
4. 推荐 0、官网引用 0；不得由 Signal 或本地测试推定增长。
5. #872 没有独立的自然 24 小时/7 天候选观察窗口。页面显示的 387.59 小时是历史累计，并明确标注不能作为当前候选验收。
6. 官网首页与根 sitemap 的生产修复仍需服务器变更授权与回滚窗口。

## 8. 安装与回滚原则

候选安装只覆盖程序文件，继续使用现有持久数据目录。安装前复制 BUILD_RECORD 和数据目录；禁止删除 Mission、Command、SEO/GEO 账本。回滚时恢复原 #872 程序文件并继续使用同一数据目录；新增字段均为兼容性字段，旧版本会忽略，不会删除历史记录。

最终生产结论必须分层：代码回归通过、Windows CI 通过、安装升级通过、用户机现场通过、真实外部平台通过、自然 24 小时/7 天通过。后一层不能由前一层替代。

## 9. #872 问题总账

| 任务项 | 本轮结论 | 是否改代码 | 当前验收层级 |
|---|---|---:|---|
| GEO 4 条旧任务安全阻塞 | 确认缺陷：唯一权威 Receipt 对账未进入 claim 主路径 | 是 | 代码、隔离回归、Windows CI 通过；现场安装后待核验 |
| SEO 自动发现/发布/提交 | 新增 35/34 账本存在；另确认 4 个已发布 Asset 元数据退化 | 是 | 5 个 URL HTTP/Canonical 现场核验；元数据修复后的生产再发布待安装后验收 |
| 社媒真实发布为 0 | 24 个账号/授权事项仍在，属于外部授权条件 | 否 | 未通过；无 Post ID/URL |
| R7 18/25 与 19/25 | 不同刷新时点，不是调度故障 | 否 | 已解释并保留独立口径 |
| Mission 1178/1185 | Mission 全账本，不能等同外部成果 | 否 | 原始账本口径正常 |
| GEO/SEO“今日发布”同名 | 两套业务集合被相同标签混淆 | 是 | UI/API 范围标记回归通过，现场待候选安装后核验 |
| GEO 待核查 78 / 技术超时 73 | 历史安全隔离，不能批量重试 | 否 | 保留，未清零、未重放 |
| GEO 24h/72h/7d | 现场为 7/13、4/13、0/13 | 否 | 自然时间验收未完成，未提前补造 |
| 稳定性 24h/7d | #872/#874 尚无独立自然窗口 | 否 | 未通过；历史累计 387.59h 不作替代 |
| 官网首页技术 SEO | 首页 Schema/canonical/OG/正文/内链及根 sitemap 仍异常 | 否 | 既有生产站问题；缺生产根站变更授权 |
| 经营归因 | 只读数据可读，但 UV/咨询/当日订单为 0，收入归因字段不支持 | 否 | 未形成推广转化闭环 |
| 外部 AI 新 Evidence/推荐/引用 | 正式基线 50/50、提及 8，推荐 0、引用 0 | 否 | 本轮未发送外部问题，未制造新 Evidence |

本轮没有改动 Mission、Command、Controller Plan、订单、资金、用户、小程序、生产数据库，也没有重试任何状态不确定的外部动作。
