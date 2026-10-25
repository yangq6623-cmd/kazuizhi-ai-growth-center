# 卡嘴子 #875 遗留故障精准收口报告

日期：2026-10-25  
基线：`#875 / f4a7731a4e5d2e0ad40cae957cf3a05f6c54a16c`  
现场：`http://127.0.0.1:8876/`

## 安全边界

本轮未创建 Mission、Command 或 Controller Plan；未清空或改写生产账本；未向外部 AI 重发历史问题；未发布官网或社媒内容；未提交搜索引擎；未访问资金、订单或用户写接口。所有写入测试均使用临时 `LOCALAPPDATA` 隔离账本。

## 现场原始证据与第一断点

| 问题 | 第一断点 | 原始证据 | 根因 |
|---|---|---|---|
| GEO `49/50` 与 `50/50` | `/api/r8-13/seo-geo` 的正式矩阵聚合 | `fast-ui=50/50`、`evidence-compact=50/50`、旧接口 `49/50`；被遗漏项为 `GEO50-D02` / `GEO-RECEIPT-08F460F93A2C` | 旧接口读取 `receipts(1000)` 活动窗口；较新的 C 级回执将一条正式 A/B Evidence 挤出窗口 |
| 历史 GEO 阻塞继续积累 | 建任务时的幂等键 | 6 条带既有 Run/Attempt、无匹配 Receipt 的任务仍为 `blocked_by_safety_gate` | 原幂等键把变化的 `plan_id` 作为基线动作身份，新 Plan 可再次创建相同 Mission/Question/Provider 动作 |
| 首页短暂 `SEO 0/0`、`GEO 0/50` | 老板总控首次渲染 | 页面刷新后仍出现假零，但同期原始 API 为 SEO `35/34`、GEO `50/50` | 首次渲染以空对象作为业务真值；较慢请求失败/取消时空值覆盖最后成功结果 |
| ChatGPT 连接页偶发“未验证” | `/api/chatgpt-control/status` 刷新失败分支 | 原始状态为 `verified=true`，详情页却可显示未验证 | 一次临时读取失败会清空已验证状态，而非保留最后成功真值并标记陈旧 |
| R7 首屏 `0/0` | 今日任务卡片初始化 | 真正快照尚未返回时先显示 0 | 加载占位符使用业务数字 0，而非未知状态 |

## 最小修改

- `core/geo_validation.py`
  - 增加完整正式 Evidence 读取函数，保留原最近活动 Receipt API 的返回契约。
  - 增加外部动作语义幂等键：Mission、Question、Provider、执行方式和复测 Schedule/父 Receipt 共同决定身份；Plan ID 变化不再制造等效外部 Task。
  - 精准对账仍只允许唯一严格匹配 Receipt 自动闭环；无/多条匹配继续安全隔离，Claim 不改写其历史记录。
- `backend/r8_13_seo_geo_patch.py`、`core/seo_geo_growth_intelligence.py`
  - 正式矩阵改为使用完整正式 Evidence Ledger，不再使用最近 1000 条活动窗口。
- `web/r8_23_growth_os.js`
  - 使用较轻量的可信 SEO/GEO 汇总作为老板总控主数据源，保留原完整接口作为兼容回退。
  - 加入最后成功快照缓存、加载态和错误保留；未知不显示为 0。
- `web/r8_10_workbench.js`
  - 连接读取失败时保留最近一次已验证状态并标记“刷新延迟”；从未取得状态时显示“未知”，不误报已验证或未验证。
- `web/r7.js`
  - 首次真实快照返回前显示 `— / 读取中`，不显示假 `0/0`。

## 隔离测试结果

| 测试 | 结果 |
|---|---|
| 完整 50 条正式 Evidence + 1000 条更新 C 级回执 | 50/50，通过 |
| 同一外部动作、不同 Plan ID 并发/重复规划 | 复用原 Task，通过 |
| 同一 24h Schedule 重复规划 | 复用原 Task，通过 |
| 不同 Schedule 的合法复测 | 创建独立 Task，通过 |
| 既有 Attempt 无 Receipt | 原记录保持不变、等效新 Plan 复用原 Task、另一条合法新任务可独立领取；零重发、零伪造 Evidence，通过 |
| 旧 808 no-replay / 新任务非阻塞 Claim 契约 | 通过 |
| #874 Snapshot、完整 Evidence、失联租约回归 | 通过 |
| R8-23 老板总控、R8-24 UI 恢复、ChatGPT 控制契约 | 通过 |
| JavaScript 语法检查 | 通过 |

GitHub Actions 的 Windows 安装、覆盖升级、数据保留、回滚与 Defender 结果以本提交对应 Workflow Run 和安装包内 `BUILD_RECORD.json` 为准；CI 成功不等于生产现场验收成功。

## 保留的真实阻塞

- 6 条历史 GEO 任务缺少唯一可核验 Receipt。它们不得重发；现状应保留安全隔离。补丁只阻止继续创建等效新任务，并确保新的合法任务可越过历史阻塞独立领取。
- SEO `SEO-50AAE9309BF1` 已发布且公网 HTTP 200，但搜索提交仍受 `publication_scope_not_approved` 范围授权限制；`SUBMITTED` 不能冒充 `INDEXED`。
- 外部社媒已验证发布仍为 0。多个 PC 渠道等待扫码/登录/验证码或平台授权，不能用本地草稿代替 Post ID/URL Receipt。
- 小程序访问 UV 不在当前经营只读数据中，不能补造。
- 新候选安装后的真实 24 小时/7 天连续运行必须按自然时间另行验收。

## 回滚

候选以 `f4a7731a` 为父提交。代码回滚可回到该提交；Windows 覆盖安装前需备份安装目录和持久化数据目录，回滚时恢复 #875 程序但继续保留持久化数据。不得回滚或删除运行期间新增的 Task、Receipt、Evidence、Asset 或经营记录。
