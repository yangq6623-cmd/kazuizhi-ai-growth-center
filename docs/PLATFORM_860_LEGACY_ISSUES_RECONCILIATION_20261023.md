# 卡嘴子 #860 遗留问题取证、定向修复与验收记录（2026-10-23）

## 1. 基线与边界

- 本机页面身份：Build #860，Commit `9f479cdcefcc1de1db222a65e4a5fce812487cd9`。
- 保留：`MISSION-20260924-DF7DB2`、`CMD-20261019-073EED`、`PLAN-D37B40F356`、全部历史 SEO/GEO/R7/R8 账本。
- 本次没有创建生产 Mission/Command，没有导入现场等待指令，没有发送外部 AI 问题，没有发布网页，没有搜索提交，没有修改订单、资金、用户或小程序数据。
- 浏览器现场先取得数据，后续 Chrome 扩展会话未继续返回可控标签页。因此没有把无法再次读取的本机原始记录推测成已验收。

## 2. 现场确认的关键证据

### SEO 第 33 条 Asset

| 字段 | 原始值 |
|---|---|
| Asset ID | `SEO-0CB250BBE457` |
| Revision | `SEO-REV-88DACE8A3C84` |
| 关键词 | 涟水县洗衣机不排水上门维修 |
| 阶段 | `QC_PASSED` |
| 公网 URL | 无 |
| 部署 Receipt | 无 |
| 搜索提交 Receipt | 无 |
| 累计口径 | Asset 33 / 公网 32 / 搜索提交 31 |

首个阻塞点不是生成或 QC，而是发布资格关联丢失：Opportunity 的 `autonomous_verified_service_intent_pool` 来源没有随新 Asset 传递；本地和远程部署器只检查 Asset/QC 事件，因而把合格 Asset 判为 `publication_scope_not_approved`。

已在隔离账本修复并验证 32/31 → 33/32；这不是生产公网成功声明。生产仍需安装候选后由原安全链取得真实 URL、部署 Receipt 和搜索平台 Receipt。

### R7 页面超时

现场同时出现：

- `/api/r7/jobs` 超时；
- `/api/r7/agents` 超时；
- 后台任务在 10 月 23 日继续更新，页面刷新后能看到当日 20 项、完成 9 项、等待 11 项。

源码复现根因：R7 页一次刷新分三批发出 5 个 GET；每个 10 秒计时器在请求进入浏览器共享两槽队列前已经启动。被其它慢请求占槽时，尚未真正发往后端的 R7 请求也会超时，页面遂把“完整状态未取得”与后台停机混在一起。

修复为一个 `/api/r7/ui-snapshot` 一致性快照，并从共享慢请求队列旁路；原 `/jobs`、`/agents`、`/engine`、`/audit`、`/model-routes` 接口继续保留兼容。

### 两类“控制总线”被混淆

页面同时存在：

1. 私有 GitHub Decision Pack 异步总线；
2. Windows 同步目录“双向运营桥/AI 指令箱”。

现场“1 条等待导入”来自第 2 类目录桥，不等同于第 1 类私有 GitHub 总线待处理项。旧 UI 将“AI 指令箱”写成“立即同步 / 查看”，点击查看实际直接 POST 同步，缺少只读核对入口。

另一个确认缺陷是：私有异步总线失败分支也覆盖 `last_sync_at`，使“最近尝试”可能被当作“最近成功”。

修复：

- 分离 `last_attempt_at`、`last_success_at`；失败保留最近成功时间；
- 旧 `last_sync_at` 继续输出，兼容旧接口；
- 同步目录指令箱显示 Command ID、来源文件、kind、标题、due_at 和解析状态的只读预览；
- 点击卡片只查看，不再隐式导入；真正导入仍必须点击独立“立即同步”。

## 3. 11 项总账

| 编号 | 当前真实状态 | 是否代码缺陷 | 处理与验收 |
|---|---|---:|---|
| P0-01 私有异步总线 | 两类总线显示混淆；失败尝试覆盖成功时间；同步目录有 1 条待导入 | 是 | 已修时间语义和只读预览；隔离 Decision Pack→Mission→Receipt 及失败恢复通过。现场 1 条未导入，真实外部往返仍待安装后验收。 |
| P0-02 SEO Asset 33 | `QC_PASSED`，无 URL/部署 Receipt/提交 Receipt | 是 | 已修 Opportunity→Asset 发布范围继承和兼容解析；隔离闭环通过；生产公网结果仍为 0，待候选安装后真实验收。 |
| P0-03 GEO 三条历史任务 | `blocked_by_safety_gate / prior_external_attempt_requires_reconciliation` | 未证明为新缺陷 | #859/#860 已具备精确 Task/Question/Provider/Run/Attempt Receipt 匹配；未取得三条现场 dry-run 原始输出，不改状态、不重发。 |
| P1-04 R7 读取超时 | 后台运行但 5 请求链偶发超时 | 是 | 改为单一一致性快照；1205 条账本、8 并发、64 次轮询通过，旧接口保留。 |
| P1-05 GEO 跨日时效 | 页面曾显示 10 月 22 日快照；10 月 23 日到期窗口需自然时间核验 | 暂未证明 | 现有实现按本地自然日、快照年龄和 15 分钟调度年龄区分；未提前复测。现场到期执行结果待真实时间/账本读取。 |
| P1-06 内容积压 118 | 体检只把 `待本地执行器/执行失败/待总控确认` 汇总为一个数字 | 信息不足 | 未批量恢复。缺少 118 项生产明细，不能给出逐项安全处置；保留为现场只读导出项。 |
| P1-07 官网技术 SEO | 7 项中 5 项仍存在，2 项已恢复 | 是（官网） | 2026-10-23 HTTP 复测：根 sitemap `text/xml` 正常；子 sitemap 33 URL 全部有 lastmod。首页缺 Schema/canonical/OG，静态 HTML 无可抓取正文和普通内链。未改生产官网。 |
| P1-08 多工作台口径 | R7 当前数据可刷新，但超时错误、旧桥/私有总线命名导致误解 | 部分是 | R7 快照带统一生成时间；两类总线改名分离。SEO/GEO/经营仍保持各自统计范围，不强行合并数字。 |
| P1-09 经营数据 | 快照截至 10 月 22 日约 13:30；推广归因字段不足 | 未证明 | 保持只读和真实截止时间；未把历史订单归因为新增推广成果。 |
| P2-10 无人值守稳定性 | #860 独立 24h/7d 证据不足 | 否（尚待自然时间） | CI/隔离故障恢复不能替代自然运行；保持待验收。 |
| P2-11 外部渠道 | 16 条路由登记，10 条可准备/工作；官网、小程序为自有已验证路由；主要社媒仍待登录/浏览器验证 | 外部授权为主 | 未绕过登录、扫码、人机或风控；草稿不计发布，未生成 Post ID/URL。 |

## 4. 官网真实 HTTP 复测

复测时间：2026-10-23 11:26—11:27（北京时间附近；响应 Date 为 UTC）。

| 检查 | 结果 | 证据 |
|---|---|---|
| 首页 | 200，`text/html` | 779 字节 app shell |
| Schema | 未通过 | HTML 无 `application/ld+json` |
| canonical | 未通过 | HTML 无 `rel=canonical` |
| Open Graph | 未通过 | HTML 无 `og:*` meta |
| 可抓取正文 | 未通过 | body 仅 noscript、`#app` 和脚本引用 |
| 普通内链 | 未通过 | 原始 HTML 无 `<a>` |
| 根 sitemap | 通过 | 200，`content-type: text/xml`，声明首页与子 sitemap |
| 子 sitemap lastmod | 通过 | 33 个 `<url>`，33 个 `<lastmod>` |

这 5 项需要官网部署仓库、备份、回滚和生产验证。本候选不擅自修改正式站点。

## 5. 修改文件

- `core/seo_geo_growth.py`
- `integrations/seo_public_deployer.py`
- `integrations/r8_17_remote_deployer_patch.py`
- `integrations/search_engine_submitter.py`
- `integrations/async_control_bus.py`
- `integrations/bridge.py`
- `core/r7_engine.py`
- `backend/server.py`
- `web/kz_async_control_ui.js`
- `web/r7_bridge_usability_patch.js`
- `web/r7.js`
- `web/build_info.js`
- `04_Build/v2/test_860_seo_publication_closure.py`
- `04_Build/v2/test_862_control_bus_r7_read_reliability.py`
- Windows CI workflow及本报告。

## 6. 自动化测试

已通过：

- #860 生产派生安全副本：新 Asset 发布、远程部署、搜索提交、幂等、未授权关键词继续阻断、32/31 历史保留；
- #862 隔离 Decision Pack 成功/失败时间语义；
- 同步目录待导入文件只读预览不导入；
- 1205 条 R7 历史任务，8 并发、64 次一致性快照；
- 旧 R8-10 async bus、R7 engine、Python compileall、浏览器脚本语法和 diff check。

PR #34 的 Windows Run `39893851912`（Build #861）已通过 #860 专项、既有 R7/R8 回归、打包、Defender、静默安装、覆盖升级、数据保留和卸载；它不包含本报告后续的总线/R7补丁，因此只作为 SEO 专项候选证据，不作为 11 项最终候选。

## 7. 未完成及现场验收门槛

1. 第 33 条 Asset 的真实公网 URL、部署 Receipt、搜索提交 Receipt 尚未产生；`SUBMITTED` 也不等于 `INDEXED`。
2. 三条 GEO Task 必须通过只读 `/api/r8-19/geo/task-reconciliation` 取得逐条匹配结果；无唯一权威 Receipt 的记录继续隔离。
3. 同步目录 1 条等待指令必须先在只读预览核对身份；未执行生产导入。
4. 私有异步总线的现场真实往返会创建/处理真实 Command/Receipt，需安装候选后在本机显式执行；隔离测试不冒充生产往返。
5. 10 月 23 日 GEO 到期复测、#860 独立 24 小时/7 天稳定性依赖自然时间，尚未通过。
6. 官网 5 项技术 SEO 需要独立生产部署授权和回滚验证。
7. 内容中心 118 项、经营数据归因和未授权渠道仍缺生产原始明细/外部条件；当前不得自动重试或宣称完成。



## 8. GitHub 与 Windows 最终候选

- PR：[#35](https://github.com/yangq6623-cmd/kazuizhi-ai-growth-center/pull/35)
- 最终分支提交：`90721efede814016eb6b4fe894b0f25e031cd472`
- Windows CI：Build #870 / Run `39912100281`，结论 `success`
- Actions：https://github.com/yangq6623-cmd/kazuizhi-ai-growth-center/actions/runs/39912100281
- PR 合并测试提交（BUILD_RECORD）：`93e547a6f8363c2d7fb753edac5648c84f93df8f`
- 安装包 Artifact ID：`12483532579`
- Artifact ZIP SHA256：`4766ec319946688bcf32793190c068a00ed70bc79a910c1fdb40394a2839389c`
- 安装程序 SHA256：`596aca46b0c90ff34852406b759e0ba07386eed22b9bfca76e2262c945ec2192`
- Defender：通过，`detection_count=0`
- Authenticode：`NotSigned`；本次仓库未启用 Azure Artifact Signing，未把未签名状态表述成已签名。
- 已通过：定向门禁、既有 R7/R8 回归、浏览器脚本、打包、Defender、静默安装、启动、覆盖升级、持久数据保留、卸载。
- GitHub Release 发布步骤按现有配置跳过；候选通过 Actions Artifact 交付。

审计保留：Build #864 因旧 R8-25 测试写死多请求实现而失败，更新为一致性快照行为契约后通过；Build #868 因报告 Copy-Item 换行格式错误而失败，安装测试已通过但产物未上传；修复后 Build #870 全部通过。两次失败均未冒充成功候选。

Build #870 只证明软件候选和升级路径通过自动化验收，不证明生产 Asset 33 已发布、三条 GEO 历史任务已对账、真实控制总线已完成现场往返，亦不证明 24 小时/7 天自然运行达标。
