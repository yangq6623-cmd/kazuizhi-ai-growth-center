# #827 原架构兼容性保护与增量加固测试报告

## 背景与目标

本报告验证本次改动没有重建平台、没有改换数据根目录，并验证 GEO 外部动作在并发领取、重启、网络中断和回执延迟时不会盲目重复发送。测试只使用临时合成账本，不连接生产 SQL Server，不提交搜索、不发布网页、不调用外部 AI。

## 代码变更

| 文件 | 增量变更 |
|---|---|
| `core/geo_validation.py` | 关联视图、幂等键、Attempt、Lease、心跳续租、过期 Lease 对账/隔离、结果不确定禁重试 |
| `integrations/geo_browser_agent.py` | 活动 Task 续租、2.2.2.828 精确 Run/Attempt 验证、旧扩展兼容 |
| `browser_extension/kazuizhi_geo/*` | 扩展 2.2.2.828；活动 Task 持久化；Heartbeat/Receipt/Block 回传 Run/Attempt |
| `core/geo_growth_orchestrator.py` | Publication Event、Schedule ID、关联下传、幂等 Task 复用 |
| `core/geo_phase3.py`、`core/geo_phase3_job_patch.py` | GEO Opportunity/Action 与既有 R7 Job 原位关联 |
| `core/seo_geo_growth.py`、SEO deployer/fallback | 真实发布 Receipt 派生稳定 Publication Event；旧资产路径兼容 |
| GitHub Actions | 新增 #827 隔离门禁、扩展打包、报告随安装包交付 |

## 已通过的隔离回归

- GitHub Actions 源码门禁清单共 78 项：本地容器通过 76 项；其余 2 项因容器无可启动 Chrome 而明确留给 Windows CI，未冒充通过。
- Python 语法编译：全部变更模块通过。
- Chrome 扩展 JavaScript 语法检查：通过。
- #827 新门禁：稳定 Schedule ID、同 Schedule 幂等 Task、双领取防护、Lease 续租、错误 Owner 拒绝、精确 Attempt Receipt、Lease 过期隔离、禁止结果不确定重试：通过。
- 73 条历史超时 + 81 条发送结果不确定合成账本保护：154 条记录在 Claim 前后逐字段一致，自动领取为 0：通过。
- 既有 GEO #812 Claim→执行→Receipt：通过。
- 既有 GEO #818 账本与三窗口安全：通过。
- 既有 GEO #824 现场真值与禁止提前复测：通过。
- R8-27 浏览器 Agent 回归：通过。
- R8-28 Chrome 扩展回归：通过。
- 808 豆包确认发送/无陈旧 Evidence/回执 fail-closed：通过。
- R8-34 SEO/GEO 闭环、R8-35 重发布对账、R8-36 真值恢复：通过。
- R7 Engine、Block A、Block B、R8-19 GEO Phase3、R8-22 自治收敛、R8-23 工作台一致性：通过。
- SEO Search Submitter 与 SEO 816 UI 审计：通过。

当前 Linux 容器没有可启动的 Chrome 可执行环境，因此两项 Selenium 真浏览器用例 `test_geo_774_async_boot_browser.py`、`test_r8_25_owner_cold_start.py` 在创建 Chrome Session 时被环境阻断；不是断言失败。它们保留在 GitHub Windows Actions 发布门禁中，必须以 Windows CI 实际结果为准，未通过前不交付安装包。

## 故障注入结果

| 场景 | 预期 | 结果 |
|---|---|---|
| 同一任务多次领取 | 只有一个执行器取得 Task | 通过 |
| 同一 Schedule 重复建任务 | 返回原 Task ID，不新增 | 通过 |
| 不同 Revision/Receipt | 生成不同 Publication Event/Schedule | 通过 |
| 心跳中断、Lease 过期、有 Receipt | 对账成功，不补发 | 通过 |
| 心跳中断、Lease 过期、无 Receipt | `UNCERTAIN + replay_blocked` | 通过 |
| 陈旧 Run/Attempt 回调 | 拒绝写入 | 通过 |
| 73/81 历史异常 | 不领取、不重试、不改写 | 通过 |
| 24h/72h/7d 未到期 | 不建立提前复测结果 | 通过 |
| 已有 Task/Signal/Receipt | 不移动窗口、不覆盖历史 | 通过 |

## 尚待 GitHub/Windows 门禁

以下结果必须等待本分支 GitHub Actions 实际运行后填写，未运行前不得写成通过：

- Windows PyInstaller/Inno Setup 构建。
- Microsoft Defender 扫描。
- Windows 静默安装、启动、覆盖升级、持久数据保留、卸载。
- 最终安装包和扩展 SHA256。
- 安装到用户本机后的版本、原始数据、目标 Opportunity/Job、首次发布时间和 24h/72h/7d 调度复核。

## 自然运行验收

- 72 小时：尚未实际经过，状态为待验证。
- 7 天：尚未实际经过，状态为待验证。
- 只有自然时间到达且账本连续、无重复外发、无提前复测、服务自动恢复、SEO/GEO/经营读取可用时，才能补充最终结论。

## 限制与验收规则

- `PUBLISHED` 必须有真实发布 Receipt 和公网核验。
- `SUBMITTED` 不等于抓取或收录。
- C 级 Signal 不等于正式 A/B Evidence。
- 数据未知显示为未知，不写成 0。
- 登录、验证码、账号风控、资金动作继续人工接管。
- 本次没有修改订单、资金、用户数据或生产 SQL Server。
