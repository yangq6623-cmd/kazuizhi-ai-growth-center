# 卡嘴子 #879 八项遗留问题集中收口报告

日期：2026-10-25（现场取证延续至 2026-10-26 北京时间）  
基线：`#879 / ebeae1b8c29f726e3530569e3ab4dfb0d5520aa3`  
现场：`http://127.0.0.1:8876/`

## 安全边界

本轮未创建 Mission、Command 或 Controller Plan；未清空、覆盖或重放生产 Task、Attempt、Receipt、Evidence、Asset；未向外部 AI 重发历史问题；未发布官网或社媒内容；未执行搜索提交；未修改订单、资金、用户或小程序写数据。代码写入测试全部使用临时 `LOCALAPPDATA` 隔离账本。

## 维修前现场真值

| 项目 | 原始现场证据 |
|---|---|
| SEO 重复部署 | 实际 Asset 为 `SEO-0A6FBE492759`（任务书少一个 F）。同一公网 URL 在 2026-10-25 19:03—20:18 产生 20 条内容刷新事件，`GEO-GROWTH-2BD2EDC55B2A` 与 `GEO3-A01-brand_visibility_missing` 交替认领同一 Asset；最后 Receipt 为 `REMOTE-DEPLOY-SEO-0A6FBE492759-20261025T201845+0800`。 |
| 老板总控读取 | R7 快照自身新鲜且可读；`/api/r8-22/autonomy` 与 `/api/r8-23/growth-os` 并发慢请求会被 15 秒轮询重复取消，页面显示 `The operation was aborted`，并清空最后成功视图。 |
| GEO 历史隔离 | 六条旧任务均各有一次外部 Attempt、无唯一匹配 Receipt，精准对账结果为 `prior_attempt_without_matching_receipt_hold`、`mutated=false`、`new_external_requests=0`。 |
| GEO 新任务 | 历史冻结任务未阻塞新任务；现场已经出现新的 24h/72h/7d 合法复测完成记录和 Evidence。 |
| SEO 总量 | 公网页面 35，搜索提交 34；`SEO-50AAE9309BF1` 已公开但无提交 Receipt，属于提交范围未授权，不是部署执行器故障。 |
| 社媒 | `/api/r8/social` 账号为空；六个平台只有软件路由登记，`external_verified=false`，真实 Post ID/URL Receipt 为 0。 |
| R7 调度 | 完整账本 1444 条，完成 1442，排队 1，人工 1，失败 0；200 条只是显示窗口，不是工作容量。 |
| 经营回流 | 只读经营快照新鲜，但渠道归因 `not_connected`；小程序访问 2，线索/需求/新订单为 0，不能归因给 SEO/GEO。 |

## 第一失败节点与最小修复

| 编号 | 第一失败节点 | 根因 | 处理 |
|---|---|---|---|
| P0-01 SEO 重复部署 | `geo_phase3_seo_bridge.prepare_phase3_assets` | 共享 Asset 在检查“该 Action 已有真实 Receipt”之前，就被当前扫描改写 `growth_action_id/content_revision_id`；两个合法来源交替改写，持续产生 `republish_pending`。 | 先按目标 Action 查完整刷新历史；已有真实 Receipt 的 Action 永久跳过。只有新且未验证的 Action 可以认领 Revision。部署器增加 Asset+Action+Revision+URL 精确 Receipt 防线及跨本地/Remote Agent/直接文件回退的同一重入锁。 |
| P0-02 总控 Abort | `r8_23_growth_os.js refresh` 与 GET `/api/r8-22/autonomy` | 15 秒定时器允许请求重叠；`Promise.all` 任一失败使整页失败；高频 GET 还会执行 Mission/Plan/Task/Receipt 收口写逻辑。 | GET 改成只读快照；前端单飞请求、最多排队一次刷新、`Promise.allSettled` 部分恢复、最后成功缓存和准确超时提示。 |
| P0-03 GEO 历史任务 | 原 Attempt 到 Receipt 关联 | 六条均缺少唯一权威 Receipt。 | 不改历史、不重发；继续安全隔离。现场证据证明新任务可独立执行，因此没有取消安全门禁。 |
| P0-04 SEO 35/34 | `SEO-50AAE9309BF1` 搜索提交资格 | 公网部署已成功，搜索提交范围没有批准。 | 正常授权阻塞，不改代码、不强制提交；`SUBMITTED` 与 `INDEXED` 继续分开。 |
| P1-05 社媒回执 0 | 账号授权层 | 软件路由存在，但六个平台均无真实登录/授权。工作台错误地把软件路由登记解释为能力就绪。 | 能力状态改为只有 `external_verified` 才 ready；显示已登记路由数、已授权路由数和 `authorization_required`。不触发发布。 |
| P1-06 指标统一 | 请求失败后的前端降级 | 未加载/失败会覆盖最后成功值并显示假零或整块不可用。 | 保留最后成功数据和采集时间；首次无真值显示读取中；同口径仍由原始账本聚合，不强行统一不同指标。 |
| P1-07 调度与积压 | R7/GEO 原始账本 | R7 正常接续；GEO 历史 Hold 不占用全局执行资格。 | 无调度代码改动；保留历史 78 条待核查与安全隔离。 |
| P1-08 稳定性/经营闭环 | 自然时间与渠道归因 | 当前进程健康不等于 24h/7d；经营数据没有 SEO/GEO 渠道归因字段。 | 不伪造通过。候选安装后重新开始自然时间验收；经营归因保持 `not_connected`。 |

## 修改文件

- `core/geo_phase3_seo_bridge.py`
- `core/seo_geo_growth.py`
- `integrations/seo_public_deployer.py`
- `integrations/r8_17_remote_deployer_patch.py`
- `integrations/r8_17_direct_file_fallback.py`
- `core/r8_22_autonomous_convergence.py`
- `backend/r8_22_autonomy_convergence_patch.py`
- `web/r8_23_growth_os.js`
- `core/r8_23_growth_operating_system.py`
- `04_Build/v2/test_879_eight_issue_closure.py`
- `.github/workflows/build_v2_enterprise_beta.yml`

## 定向与兼容回归

修复前，生产形态测试可复现：共享 Asset 的已验证 Action A 会覆盖当前 Action B 并再次进入部署。修复后，同一计划连续运行四次均不改写 Revision、不设置 `republish_pending`、不新增 Publication Event；精确历史 Receipt 只做本地对账，`external_request_created=false`；不同的新 Revision 仍可合法进入部署。

已经通过的隔离回归包括：

- `test_879_eight_issue_closure.py`
- `test_875_precision_closure.py`
- `test_r8_22_autonomous_convergence.py`
- `test_r8_23_final_workbench_parity.py`
- `test_r8_17_autonomy_remote_bridge.py`
- `test_857_continuous_closure_acceptance.py`
- `test_859_closed_loop_repair.py`
- `test_860_seo_publication_closure.py`
- `test_872_seo_metadata_recovery.py`
- GEO Claim/no-replay、SEO QC/部署/提交、R8-14/15/16/20/23/25/34/35 相关回归
- `node --check web/r8_23_growth_os.js`
- `git diff --check`

最终 Windows 安装、覆盖升级、持久数据保留、卸载/回滚和 Defender 结果，以本提交对应 GitHub Actions Run 与安装包内 `BUILD_RECORD.json` 为准。CI 成功不等于用户本机或生产外部平台验收成功。

## 仍未关闭的外部/自然条件

- 六条历史 GEO 请求缺少唯一 Receipt，只能永久安全隔离或等待将来取得权威证据，禁止重发。
- `SEO-50AAE9309BF1` 缺少搜索提交范围批准。
- 社媒六个平台没有已验证账号会话；需要各平台正常登录/扫码/验证码/最终发布授权后才可做真实 Post ID/URL 验收。
- Google 抓取、收录、曝光、点击，外部 AI 推荐/引用以及经营转化均没有新增真实证据。
- 候选版本的 24 小时和 7 天连续运行必须在安装后按自然时间重新计时。

## 覆盖安装与回滚

候选以 `ebeae1b8` 为父提交。覆盖安装前备份当前 #879 程序目录与持久化数据目录。回滚只替换程序文件回到 #879；运行期间新增的 Task、Attempt、Receipt、Evidence、Asset 和经营快照必须继续保留，不得用旧备份覆盖新账本。
