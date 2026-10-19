# R7/R8 原架构保护清单与 #827 增量加固说明

## 1. 背景、目标与边界

本专项不是重构。目标是在原 R7/R8 源码、API、JSON 账本、8 名 AI 员工、Windows 服务和 SEO/GEO 业务链上补齐关联、租约及结果不确定保护。数据根目录仍是：

`%LOCALAPPDATA%\Kazuizhi_AI_Enterprise_V2.0.0_Beta\data`

所有 JSON 写入继续经过 `core/storage.py` 的进程内 `RLock`、同目录临时文件、`fsync` 和 `os.replace`。没有建立新数据库，没有迁移或清空历史账本。

## 2. 原有模块与保护清单

| 模块 | 主要源码 | 主要入口/API | 原数据与回执来源 | 现状 |
|---|---|---|---|---|
| R7 任务调度 | `core/r7_engine.py`、`backend/r7_patch.py` | `/api/r7/jobs`、`/api/r7/engine`、`/api/r7/agents`、`/api/r7/audit` | `r7/jobs.json`、`r7/audit.json`、`r7/migration.json`；本地执行回执嵌在 Job | 已实现并保留 |
| R7 8 名员工 | `core/r7_engine.py`、`core/daily_workforce.py` | `/api/r7/agents`、日程/队列入口 | `r7/workforce_schedule.json`、R7 Job | 已实现并保留 |
| Command/控制总线 | `integrations/async_control_bus.py`、`integrations/chatgpt_control.py`、`core/command_execution.py` | 控制总线及 R8-22 汇总接口 | `r8_10/async_control_bus_state.json`、`r8_10/async_control_bus_receipts.json`、ChatGPT 控制账本 | 已实现并保留 |
| Mission 主链 | `core/mission_ledger.py`、`core/r8_22_autonomous_convergence.py`、`backend/r8_22_autonomy_convergence_patch.py` | `/api/r8-22/autonomy`、`/events`、`/receipt`、`/run` | `r8_11/mission_ledger.json`、`r8_11/last_nonempty_mission.json`、`ops/r8_22_autonomous_convergence.json` | 已实现并保留 |
| 8 员工增长操作系统 | `core/r8_23_growth_operating_system.py`、`backend/r8_23_final_growth_os_patch.py` | `/api/r8-23/growth-os`、`/capabilities`、`/utilization` | `ops/r8_23_growth_os.json`、R7 Job、Mission | 已实现并保留 |
| SEO 发现到资产 | `core/seo_geo_growth.py`、`core/seo_geo_autonomy.py` | `/api/r8-13/seo-geo/run`、`/api/r8-20/seo-geo`、`/refresh` | `r8_13/seo_geo_growth.json`、`r8_14/seo_geo_autonomy.json` | 已实现并保留 |
| 官网真实发布 | `integrations/seo_public_deployer.py`、`integrations/r8_17_direct_file_fallback.py` | SEO 自治周期内部调用、部署状态接口 | `r8_15/seo_public_deploy.json`、`r8_15/seo_public_deploy_receipts.json`；公网 HTTP/canonical/schema/robots 核验 | 已实现并保留 |
| 搜索提交 | `integrations/search_engine_submitter.py` | SEO 自治周期内部调用、提交状态接口 | `r8_16/search_submitter.json`、`r8_16/search_submission_receipts.json`；IndexNow/Search Console 回执 | 已实现并保留 |
| GEO 50 问及正式 Evidence | `core/geo_validation.py`、`core/geo_domestic_matrix.py`、`backend/r8_19_geo_validation_patch.py` | `/api/r8-19/geo/*`、`/api/r8-26/geo/domestic-matrix` | `geo_validation/question_set.json`、`queue.json`、`receipts.json`、`audit.json` | 已实现并保留 |
| GEO 浏览器执行器 | `integrations/geo_browser_agent.py`、`browser_extension/kazuizhi_geo/*` | `/api/r8-27/geo-browser-agent/{register,heartbeat,claim,receipt,block,disconnect}` | `r8_27/geo_browser_agent.json`、GEO Queue/Receipt | 已实现；本次原位补强 |
| GEO Opportunity 与复测 | `core/geo_growth_orchestrator.py`、`core/geo_phase3.py`、`core/geo_phase3_job_patch.py` | `/api/r8-24/geo-growth/*`、`fast-ui`、`start/pause/resume/run/retry` | `geo_validation/growth_orchestrator.json`、`phase3.json`、R7 Job、GEO Task/Receipt | 已实现；本次原位补强 |
| 运行健康与守护 | `core/runtime_resilience.py`、`core/runtime_supervisor.py` | `/api/r8-20/runtime-health`、监督状态入口 | `r8_20/runtime_health.json`、`r8_25/runtime_supervisor.json`、`r8_25/service_install.json` | 已实现并保留 |
| 经营只读数据 | `integrations/business_data.py`、`integrations/wechat_mini_program.py`、`analytics/business_metrics.py` | `/api/business-source/status`、`/api/business-analytics` | `integrations/business_source.json`、`business/remote_summary.json`、小程序汇总 | 已实现；SQL Server 保持只读 |
| 验收账本 | `core/phase1_acceptance.py` | `/api/r8-25/phase1-acceptance`、`/history`、`/start` | `r8_25/phase1_acceptance.json`、`phase1_acceptance_history.json` | 已实现并保留 |

## 3. 原有调度、恢复、去重、重试与熔断

| 机制 | 原实现事实 | 判断 |
|---|---|---|
| R7 到期领取 | `run_due_jobs()` 只领取 `queued + local + due_at<=now`，先核验 ChatGPT Command 绑定 | 已实现 |
| R7 中断恢复 | `recover_interrupted()` 把本地 `running` 恢复到 `queued`；资金任务转人工 | 已实现，但外部动作不能沿用这种直接重排语义 |
| R7 自动重试 | 本地非资金任务最多 2 次 | 已实现；只适合确定失败的本地动作 |
| R7 审计 | SHA256 前向哈希链，完整性失败停止写入 | 已实现 |
| Mission 断点恢复 | 只在本地 Mission/活动索引都为空时，从最近非空快照恢复；不生成外部成功 | 已实现 |
| SEO 发布门禁 | 真实部署 Receipt 与公网核验分离；发布不等于搜索收录 | 已实现 |
| 搜索提交退避 | 按认证、额度、网络、拒绝分类；使用 `next_retry_at`，不批量重放历史页面 | 已实现 |
| GEO 原子领取 | Queue 读写使用同一 JSON I/O 锁；正式证据按 Task 幂等 | 已实现 |
| GEO 历史保护 | Receipt 对账只恢复存在唯一权威回执的记录；模糊超时不重发 | 已实现 |
| GEO 首次发布时间 | #827 已有首次有效公网时间固定与重复核验不重置逻辑 | 已实现；本次补强事件 ID 和调度关联 |
| Windows 守护 | 用户计划任务模式；15 秒探测，进程停止后拉起；运行心跳落盘 | 已实现 |
| 模块隔离 | SEO/GEO/运行健康分别保存状态，单一接口异常不应写成全局成功 | 部分实现；需要自然运行继续验证 |

## 4. 本次原位补强内容

### 4.1 统一关联，不改旧字段

GEO 新任务及回执新增兼容字段：

`mission_id → opportunity_id → action_id → task_id → attempt_id → content_revision_id → publication_event_id → publication_receipt_id → schedule_id → receipt_id`

- 旧扁平字段继续保留。
- 新增 `correlation` 只是同一记录的可读关联视图。
- 历史 JSON 不执行批量回填；读取旧记录时允许字段为空。
- R7 GEO Job 只在创建时增补 Opportunity/Action/幂等键，不替换 R7 状态模型。

### 4.2 唯一执行归属与租约

- GEO Claim 创建唯一 `run_id`、`attempt_id` 和 180 秒 Lease。
- Chrome 扩展 2.2.2.828 保存活动 Task，在心跳中携带 Task/Run/Attempt 并续租。
- 2.2.2.828 的 Receipt、Block、Heartbeat 必须包含精确 Run/Attempt；旧 808/814 协议仍可兼容运行。
- 错误执行器、过期 Run、过期 Attempt 无权续租或提交回执。

### 4.3 结果不确定时禁止盲重放

- Lease 过期且存在权威 Receipt：只对账为成功，不创建新 Evidence。
- Lease 过期且没有 Receipt：状态进入 `UNCERTAIN`，设置 `replay_blocked=true`，转人工核查。
- 超时、未确认提交、抓取失败、连接重置等外部结果不确定错误禁止自动重试。
- 73 条历史超时和 81 条发送结果不确定记录没有迁移、删除或重试；发布门禁用 154 条合成同类记录验证其不会进入 Claim。

### 4.4 发布事件与复测 Schedule

- 每次取得真实新发布回执时生成稳定 `publication_event_id`。
- 每个 24h/72h/7d 窗口生成稳定 `schedule_id`。
- 同一 Revision、发布 Receipt、窗口重复调度只复用原 Task ID。
- 已存在 Task、Signal、Receipt 或完成记录的窗口不改写到期时间。
- 重复核验同一内容不会创建新的发布事件，也不会重置首次有效公网时间。

## 5. 已实现、部分实现、尚未完成

| 能力 | 状态 | 说明 |
|---|---|---|
| 原 R7/R8/8 员工/SEO/GEO/Windows 入口兼容 | 已实现 | 未更换入口和数据根目录 |
| GEO Task 唯一 Claim、Lease、心跳、精确 Attempt | 已实现 | 新扩展 2.2.2.828 生效 |
| GEO 结果不确定隔离、原 Receipt 优先对账 | 已实现 | 禁止自动重发 |
| Publication Event 与复测 Schedule 关联 | 已实现 | 只对新事件增补；历史不强制迁移 |
| 全平台所有旧 Task 的统一状态枚举 | 部分实现 | GEO 提供 additive `normalized_state`；旧状态仍是权威写入语义 |
| 所有历史记录完整补齐十级关联 | 未实施（有意保护） | 缺少原证据的字段保持空，不伪造关联 |
| 外部 AI 全自动正式验证 | 部分实现 | 有浏览器矩阵和 Evidence 门禁；登录、验证码、风控仍需人工 |
| SEO 收录、AI 引用、经营转化闭环 | 部分实现 | 接口和阶段已分开；当前真实收录/引用/转化证据不足 |
| 72 小时无人值守 | 待自然时间 | 代码/CI 不能代替真实经过 72 小时 |
| 7 天无人值守 | 待自然时间 | 2026-10-19 尚未经过 7 天，禁止宣称通过 |

## 6. 回滚与数据保护

1. 稳定回滚基线是 GitHub commit `f541ac88e6df98e278a7a9c1f02ac10d2092a4ef` 对应 #827 候选源码。
2. 安装包覆盖升级不得删除 `%LOCALAPPDATA%` 数据目录。
3. 新字段均为可选；回滚旧程序时旧读取逻辑会忽略这些字段。
4. 不回滚或覆盖新增期间产生的 Task、Receipt、Signal、Opportunity；程序回滚与数据删除是两件事。
5. 若新候选失败，只回滚可执行文件/安装目录，保留数据目录并先导出只读快照。

## 7. 验收输出

对应自动化门禁为 `04_Build/v2/test_r8_37_compatibility_hardening.py`，同时继续执行已有 R7、R8、SEO、GEO、浏览器扩展、Windows 安装升级与卸载回归。任何外部发布成功、收录、引用、咨询、订单结果仍只接受真实回执。
