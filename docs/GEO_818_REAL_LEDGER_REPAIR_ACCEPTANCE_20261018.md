# 卡嘴子 GEO #818：原始账本修复、Windows 构建与验收说明（2026-10-18）

## 背景与真实证据
- 原始诊断 ZIP：`KZ817_GEO_READONLY_20261018_170741.zip`，用户私有，**严禁提交仓库/日志/公开 PR**。
- 2026-10-18 17:09 北京时间，用户本机 #817 导出：859 任务（770 succeeded、73 authorization_required、14 failed、1 paused、1 queued），847 Receipt，302 个历史 Opportunity（289 superseded、13 当前有效）。
- 73 个 authorization_required 实际失败原因为 71 个 agent_response_timeout 和 2 个 signal timed out；这些不应显示为 73 次真正登录失败，更不能直接重发。
- 24h 复测槽 13 个关联，归属于 11 个唯一 Task/Receipt；其中有 failed 状态但存在 Receipt 的历史冲突记录。旧机会 superseded 后不应抹去历史 C 级结果；同一个 Receipt 不能重复计数。
- Chrome 双窗口出现 11/12、5/13、0/0；诊断时本机 fast-ui GET 20ms，而 Chrome 曾 5s 超时，属于需要标明快照质量的间歇性传输问题。
- SEO 自治 `enabled=true`、`mode=autonomous`、周期 1508，不允许在 GEO 修复中回退；正式 GEO 50/50 A/B 必须保留。

## 目标
1. 73 个历史阻塞行仍保持原始 `authorization_required`、ID/证据/发送状态不可变，但 UI 与只读证据端点按原因区分技术超时、真正登录/风控及未知。
2. 运营 C 级 24h/72h/7d 按唯一、真实成功 Task/Receipt 统计；旧 superseded 的成果提供**独立历史账本视图**，不冒充当前有效机会、不重复计数、不冒充正式 A/B。
3. 新 GEO 复测必须按机会和时间窗口创建独立任务，阻止串用旧任务；已存在的不确定外发旧任务不得重新提交。24h 完成不应阻止 72h/7d 到期继续调度。
4. fast-ui 超时后优先保留上次**注明时间且标记降级**的完整快照；若没有可信明细，显示「待同步」，不创造 0/0。
5. 保持 SEO 自治状态、Google Search Console、已有公开页面和 GEO 正式 50 Evidence 完全不变。

## 代码结构与实施步骤
- `core/geo_validation.py`：纯只读 `classify_blocked_tasks`，合并已有阻塞诊断规则，严格不重试。
- `backend/r8_20_seo_geo_growth_patch.py`：独立从原始 queue 快照读取真实分类与队列路由，精简接口携带去重历史结果，健康回退不补假零。
- `core/geo_growth_orchestrator.py`：历史独立 C 级记录、当前独立成功数、每机会独立 mission、legacy 任务防重放，已完成窗口继续 72h/7d 追踪；减少重复 Receipt 读取。
- `core/geo_autonomy.py`：允许明确归属的新任务走专属运营复测通道，继续保持原有基线冷却和单轮保护。
- `web/geo-growth-os.js`：保留已验证快照，出错明示降级与历史回执计数，不冒充新曝光。
- `04_Build/v2/test_geo_816_operating_retest.py`：增加真实分布的**合成**回归用例；不会接外部平台，也不会接触用户生产数据。
- `04_Build/v2/test_geo_817_retest_ui.cjs`：前端 5 秒超时/回退防虚假 0/0 用例。

## 限制与安全
- **绝不**写入或清空用户的 queue、Receipt、Evidence、历史重试计数；不自动复发状态不确定的外部问题；不触发验证码/账号风控绕过。
- 72h/7d 仍需真实时间到期及真实 C 级回答；没有回执不能标记成功。
- Superseded 记录依然存在原始 JSON，历史指标标记 `retained_opportunity_history`，不等于永久留存或自然曝光。
- 不将 API C 级或 SUBMITTED/旧页面重发布记为正式 A/B、收录、点击、咨询、订单。
- 不能拿 Linux 单元测试代替 GitHub Windows 安装、覆盖升级与数据保留验证。

## 验收标准与测试门禁
- 回归：71+2 个历史超时必须标识为技术待审，而不是账号授权；真正登录仍单独识别；原始任务不变。
- 去重：13 个历史槽的重复引用按唯一成功 Task/Receipt 计数，失败但有 Receipt 不增加成功数。
- 安全：旧没有绑定 Opportunity 的在途任务阻止新任务重新发送；不同新 Opportunity 绑定不同 mission；Chrome 老 814 扩展可继续工作。
- 时序：24h 已完成仍在 72h/7d 到期后推进；未到期不抢跑。
- UI：保留旧可信快照并显示降级/时间；没有可信数据一律待同步。
- Windows：原有 SEO/GEO、浏览器安全领取、独立云端复测、HTTP 并发、部署/覆盖/卸载和持久数据测试全部通过。
- 交付：提供 GitHub Actions Windows 运行详情、安装包下载途径、SHA/Commit、未通过限制；只有绿色验收才能交付候选安装包；用户本机正式 24h/72h/7d 外部效果仍需后续真实运行观察。

## 版本与回滚
- 原生产用户安装版本：#817，commit `c7764e59`；不主动覆盖、卸载或修改。
- 开发：`codex/818-geo-ledger-truth-20261018`，基于上一轮 `codex/817-runtime-acceptance-20261018` 已验收的候选 UI 修复。
- 本分支代码经过 Windows CI 才能创建下载产物；若 CI 红色则停止交付并修正后重跑。
- 不涉及 SQL 迁移。回滚保持 #817 原安装和持久化数据。
