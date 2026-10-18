# Codex执行说明 / #808 GEO集中修复与验收

## 背景
卡嘴子AI工作台#807已经安装，Chrome国内GEO执行器扩展版本2.2.2.808，五平台状态ready且定时器心跳持续刷新。但GEO当前机会池13、等待复测13、正式新Receipt未确认增长。2026-10-17只读审计 `/api/r8-19/geo/audit?limit=500` 显示26条历史Receipt严格匹配状态已修复（先备份），余73条阻塞中回答超时71、信号超时2，另有`geo_task_claimed`、`geo_task_transition`、`geo_stale_task_recovered`。页面50/50历史概览不等同本轮外部Evidence。

## 目标
在不重发73条不确定已发送的问题前提下，让现有Chrome 2.2.2.808能领取合法的、分配到正确平台的首次任务；不被其他平台队列饿死，安全完成唯一的新豆包问题端到端试跑；首页直接可读失败原因、上一领取任务、外部回执时间。

## 文件结构
- `05_V2.0.0_Source/core/geo_validation.py`：精确目标平台、仅未尝试任务的领取过滤；保留其他非浏览器旧调用兼容；一次性豆包任务允许与非豆包工作共存，但禁止与正在执行的豆包任务并发。
- `05_V2.0.0_Source/integrations/geo_browser_agent.py`：认证、心跳和扩展版本门禁；豆包一次性任务优先创建/领取；保留旧工作队列；公开上次领取和跳过原因（不含token）。
- `05_V2.0.0_Source/web/geo-growth-os.js`：GEO高级面板直接显示代理上次领取、跳过原因、豆包试跑状态及外部回执时间，不把诊断当Evidence。
- `04_Build/v2/test_geo_808_browser_claim_truth.py`：Windows上严谨测试其他平台排队、历史已尝试/超限、单次试跑优先级、无重复问题、无伪Evidence、独立代理状态。
- `.github/workflows/geo_808_claim_safety_preflight.yml`：Windows专项回归。
- `.github/workflows/build_v2_enterprise_beta.yml`：完整Windows安装/升级/回退回归。

## 步骤
1. 读取此文档和仓库相应文件，查看本分支相对#807的改动。
2. 运行Python syntax、808场景测试、807历史对账测试、R8-27代理兼容测试、R8-28 Chrome扩展结构/JS校验。
3. 专项Windows通过后，合并到 `codex/r8-28-persistent-browser-agent-788-20261011` 并运行完整构建。构建编号应为#808；不要擅自升级Chrome扩展版本，保留2.2.2.808。
4. 实际安装后验收 `/api/r8-19/geo/queue`、`/api/r8-19/geo/audit?limit=500`、`/api/r8-19/geo/recovery-preview`、`/api/r8-27/geo-browser-agent/status`。
5. 当Chrome认证代理在线且存在从未在豆包尝试的50问时，持久化最多一次全新试跑，取得真实HTTPS会话URL和匹配原始回答才允许记Receipt。校验状态字段 `last_canary_reason` / `last_claim_reason` / `last_task_id` / `last_result_at`。如果已经预留但失败，禁止自动再次发送，需明确展示。

## 限制
- 不要重新安装Chrome扩展、不改小程序、不清空旧50问/797条历史任务、不人为制造正式Evidence。
- 通用`browser_external_ai`任务只有`expected_platform`明确且未尝试过才能发给对应浏览器；`cloud_auto`/未标记目标平台/重试次数>0或有既往run/start标记的任务不能走新执行器。
- 浏览器的ready和心跳不是完成证据；本地模拟C级不能冒充正式A/B。
- 不把提交/发布/索引/AI提及/业务转化混淆，不宣称Windows自动化现场验证已通过，除非有实际外部Receipt。
- 默认不修改现有云API/密码和授权设置。对超时不明任务不批量重试或重复提交。

## 验收标准与完成输出
- 独立专项Windows测试success+完整Windows Installer构建success，包含覆盖安装和卸载烟测；
- 一次性新任务不被非豆包队列阻塞、严格最多一次，不被之前超时问题替换，跨平台任务不能错领；
- 失败/阻塞原因可查询，且不清空上一真实回执时间；所有测试历史模拟只作用隔离临时数据；
- 输出GitHub Actions run、最终ZIP、具体SHA、适用Chrome扩展版本及本机真实验证待办。
