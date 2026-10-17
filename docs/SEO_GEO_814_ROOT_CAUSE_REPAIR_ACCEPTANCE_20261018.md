# SEO/GEO #814 底层故障根因、修复与验收说明（2026-10-18）

## 背景
用户当前本机运行 #813（65f0c327），GEO 主 Evidence 4/4 与历史 50/50 可读，但点“诊断读取”后独立 evidence-health 会 8 秒超时；代理状态 GET 仍曾 5 秒超时。Chrome 五平台 ready 仍报豆包 `question_not_submitted`。SEO 公网/提交31/30，但当前 Mission 已验证平台发布0、20任务待办、118 AI内容待恢复、214草稿待审核、官网技术SEO 7项已报告。不得将提交/草稿当公开发布。

## 根因分析
1. 页面 `web/build_info.js` 全局同源API预算只有2个槽，#811仅放行 `evidence-compact` 与 `phase1-acceptance` 两条快照；代理状态、fast/evidence/http-health与liveness仍可排在无关耗时请求后，客户端AbortController倒计时早已开始。因此轻量GET本身不用很慢也会发生5/8秒排队超时。
2. `content-agent.js` 豆包Send按钮名称正则错误地匹配字面 `\\s` 而不是空白；未找到真实发送按钮时仍触发不可信合成Enter并回报true。提问确认依赖未归一化的字串回显，空格/换行排版会造成误判。
3. `startExecution`原先在12秒未确认时直接清理浏览器执行会话，无法检查之后才出现的网页真实回显；如果重新发问会造成重复外部操作。#814改为会话仍在、仅在同一会话内重查45秒，始终只按真实页面回答生成Receipt。
4. SEO的7项官网问题是公网内容/标签层；仅修复客户端GEO不能令网站自动增加canonical/schema/OG。当前对公网根页、robots、sitemap的外部只读检查因不可访问未能现场确认，所以不能擅自修改服务器或宣称7项已解决。SEO内容和待办数量属于不同队列且可能重叠。

## 修复内容
- 精确放行7条只读GET轻量接口（其他同源API GET/POST及任务领取仍受双槽预算），保留原Evidence缓存和超时保护。
- 豆包发送仅使用明确发送按钮或form.requestSubmit，不使用合成Enter；修正空白字符识别；问答内容在展示上存在空格/换行时也能正确比对。
- 问题发送后12秒还未确认：状态 `uncertain`，不能立刻视作成功；Chrome在45秒内只做 `kz-recheck-post` 观察而不重发，确认后才进入完整原始回答采集，超时后仍不记Evidence。
- 单独发行Chrome扩展 `2.2.2.814`；Windows桌面程序升级不等于Chrome已更新，现场必须按用户授权重新加载扩展或替换更新包后核对版本。
- 无任何新AI结果伪造，不更改73条旧超时任务与10条 cloud_auto/api 排队任务，不批量重发，不修改真实SEO站点和经营账本。

## 内部测试
1. `node 04_Build/v2/test_geo_814_diagnostics_budget.cjs`：后台已有2慢请求时，7条健康/代理只读GET共700次不排队，POST仍在请求预算内。
2. `node 04_Build/v2/test_geo_814_doubao_reconcile.cjs`：无真实Send按钮拒绝合成发送；问题空白差异和回显延迟仍可确认；未出现新回显或Composer未清空时不得产生成功；同一会话只send一次。
3. 执行原 `test_geo_extension_808.js`、#811 100次/200并发、#812 自动领取与幂等Receipt、R7/R8完整回归、JS语法、Windows安装/覆盖/卸载与完整性测试。
4. **现场真实性门禁**：安装与更新Chrome扩展后必须取得新的一条独立AI会话URL、原始回答、任务ID、Receipt ID；主证据50/50不增也可以，新的复测Receipt不能当新增正式基础题位。全新任务遇到风控停止，不应自动重发。
5. 连续24小时CPU/内存/请求响应、后台心跳、受控任务领取、Evidence的状态差异；不通过不能宣称无人值守已生产就绪。

## 输出与限制
若CI失败则修复分支继续修改、不交安装包。CI通过只代表隔离Windows测试成功，网站SEO发布真实性、Chrome浏览器真实提交及长期稳定性仍需现场验收。PR保持draft；原#813留作回滚，资金操作不自动执行。
