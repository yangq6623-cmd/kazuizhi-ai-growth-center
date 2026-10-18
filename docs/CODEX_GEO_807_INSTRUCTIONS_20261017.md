# Codex执行说明：卡嘴子 #807 历史GEO超时队列安全修复

## 背景
#806本机已证实3分钟自动循环、Chrome扩展2.2.2.808的1分钟心跳和5/5平台就绪。
2026-10-17真实只读接口 `/api/r8-19/geo/queue` 看到797项：
succeeded 686 / failed 11 / paused 1 / authorization_required 99 / queued 0 / running 0。
99条为71个 `capture_failed:agent_response_timeout` 与28个 `capture_failed:signal timed out`。
按平台：doubao_web 96、cloud_auto 2、so360_ai_search 1。
其中34条带evidence_id、26条带历史官方标记，另有5条同问题同平台已有成功任务。
这是**历史超时与任务状态不一致**，不能据此断言现行Chrome 2.2.2.808新一轮仍出错，更不能批量重发。

## 目标
1. 对99个阻塞任务只做安全诊断。
2. 对确实拥有唯一、同task_id/evidence_id/question_id/provider匹配、可读原始回答与HTTPS会话URL的历史记录恢复为内部 `succeeded`，不创建新Receipt、不改变A/B/C正式证据分级。
3. 恢复前对原queue.json全量快照备份；可幂等重试恢复代码本身（不能重问外部AI）。
4. 其他超时记录不批量恢复、不重复发送，按技术待复核保留。
5. 当队列确实为空、扩展2.2.2.808有合法授权及心跳时，仅为豆包自动创建一个从未尝试过的GEO50问题做端到端试跑；本机持久标记保证绝不创建第二条，若无全新问题则安全跳过。
6. 完整Windows安装包回归构建，继续使用已通过的Chrome 2.2.2.808，不强迫重复加载扩展。

## 文件结构
- `05_V2.0.0_Source/core/geo_validation.py`：历史账本只读分析、备份恢复、一次性全新问题任务选择。
- `05_V2.0.0_Source/integrations/geo_browser_agent.py`：认证代理只在队列空、用户授权平台ready、扩展版本808时尝试一次性新问题。
- `05_V2.0.0_Source/backend/r8_19_geo_validation_patch.py`：启动时只恢复原始Receipt严格匹配的旧任务，提供只读诊断与确认保护接口。
- `04_Build/v2/test_geo_legacy_reconciliation_807.py`：状态、快照、幂等、证据真实性、唯一新问题的回归测试。
- `.github/workflows/geo_legacy_reconcile_807_preflight.yml`：专项Windows前置回归。
- `.github/workflows/build_v2_enterprise_beta.yml`：完整安装和升级验证。

## 执行步骤
1. 必须读取现有源码和本交接说明；不要猜测最近的报错是新版本产生。
2. 在独立修复分支运行安全回归、老版本兼容测试及语法检查。
3. 安装包与完整构建必须通过 Windows 安装、覆盖旧版、启动/卸载、安全扫描。
4. 安装#807后读取 `/api/r8-19/geo/recovery-preview`、`/api/r8-19/geo/queue`、`/api/r8-27/geo-browser-agent/status`；核对真实变化与原始 Receipt，不把状态修正当作新增外部曝光。
5. 真正豆包测试必须看到新问题提交，网页出现对应新回答，且只保存唯一回执；无确认则保留技术失败。
6. 7天无人值守与网站索引状况仍需分别评价。

## 限制
- 不清空99项、不自动重试不明历史超时、不强行绕过登录验证码。
- 不删50问、历史任务、回执或品牌SEO数据；不将C级辅助信号升级为正式A/B。
- 不在正式工作中注入虚假Answer、fake URL或伪造Receipt。
- 一次性新试跑只选历史从未在doubao_web/doubao_search出现的问题，且不能因中途崩溃再试第二条。
- 不能宣称本机真实自动发送已通过，除非可复查外部回执；GitHub单元测试≠本机真实验证。

## 验收与交付
- 试验数据证明有Receipt才允许恢复，无匹配则原状态保持。
- 备份先于修正，第二次运行没有再次变更。
- 当前完整队列可核对全量总数及分级。
- 单次真实试跑严格1次上限。
- 完整Windows构建success后交付GitHub安装包、测试链接、备份路径和结果报告。
