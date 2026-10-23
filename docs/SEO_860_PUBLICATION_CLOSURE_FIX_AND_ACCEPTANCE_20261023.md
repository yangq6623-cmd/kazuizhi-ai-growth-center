# #860 SEO 新 Asset 公网发布闭环专项修复与验收

日期：2026-10-23  
基线：已安装 #860，Commit `9f479cdcefcc1de1db222a65e4a5fce812487cd9`  
修复分支：`codex/860-seo-publication-closure`，PR [#34](https://github.com/yangq6623-cmd/kazuizhi-ai-growth-center/pull/34)  
范围：只处理 SEO 新独立 Asset 从 `QC_PASSED` 到真实发布与搜索提交的阻塞。

## 1. 现场目标资产

| 字段 | 原始证据 |
|---|---|
| Asset ID | `SEO-0CB250BBE457` |
| Revision | `SEO-REV-88DACE8A3C84` |
| 关键词 | `涟水县洗衣机不排水上门维修` |
| 区域 / 服务 | 涟水县 / 家电维修 |
| 创建时间 | 本机页面确认属于 2026-10-22 当日新增；页面没有展示秒级 `created_at`，浏览器直接打开只读 API 被客户端拦截，因此不伪造精确时间 |
| 当前阶段 | `QC_PASSED`（质检通过） |
| 页面下一步 | 等待公网部署与验证 |
| 公网 URL | 无 |
| 发布 Receipt | 无 |
| 搜索提交 Receipt | 无 |

同期本机真实汇总为：Asset 33、独立公网 URL 32、搜索提交 31、今日公网发布 0、今日 URL 提交 0。公网发布器、Remote Agent、IndexNow/Bing 与 Search Console 连接项显示已接通，所以首个阻塞阶段不是生成、QC 或连接器离线，而是发布资格判定。

## 2. 根因

`#859` 的增量发现把可信来源 `autonomous_verified_service_intent_pool` 写在 Opportunity 上。既有 `plan_today()` 创建 Asset 时没有把该来源和发布资格写进 Asset；本地与 R8-17 Remote Agent 发布器又只检查 Asset/QC Event 上的资格。因此该资产虽然来自限定的涟水真实服务词池并已经 QC 通过，仍永久进入 `publication_scope_not_approved`，不会进入发布领取。

这是程序缺陷，不是正常排程等待、搜索平台限额或人工授权状态。

## 3. 最小修复

- 新创建的限定增量 Asset 继承 Opportunity 来源和精确发布资格。
- 对已经存在的 #860 资产，仅在内存中按 `Opportunity ID + 涟水县 + 精确关键词/服务白名单 + 精确来源` 恢复资格，不回写或改造历史账本。
- 本地 IIS 与 R8-17 Remote Agent 使用同一资格解析函数。
- 真实发布成功后，把资格来源写进 Deployment Receipt/PUBLISHED Evidence，供后续搜索提交继续核验。
- 搜索提交器使用同一关联规则；仍必须先有 HTTPS 公网 URL 和真实提交端点接受回执。
- 未在精确白名单中的自由关键词继续被拒绝。

未修改 GEO、Mission、Command、B02/B03、订单、资金、用户、小程序或外部 AI 队列。

## 4. 修复前后复现

使用生产账本结构的隔离副本（32 个已公开、31 个已提交历史资产，以及目标 Asset/Opportunity）测试：

| 项目 | 修复前 | 修复后 |
|---|---|---|
| 目标资格 | `False` | `True`，仅因精确 Opportunity 关联 |
| 本地发布路径 | 不领取 | `QC_PASSED → PUBLISHED` |
| Remote Agent 路径 | 不领取 | `QC_PASSED → PUBLISHED` |
| 搜索提交路径 | 无目标 | `PUBLISHED → SUBMITTED`（HTTP 双桩接受回执） |
| 隔离汇总 | 32 / 31 | 33 / 32 |
| 重复运行 | 不适用 | 0 个重复发布、0 个重复提交 |
| 非白名单关键词 | 拒绝 | 继续拒绝 |
| 历史资产 | 32 条 | 全部保留 |

上述 33/32 仅是隔离测试结果，不是生产增长。

## 5. 测试结果

通过：

- `test_860_seo_publication_closure.py`
- R8-14 SEO/GEO autonomy
- R8-15 guarded deployment、server bootstrap
- R8-16 truthful search submission
- R8-17 autonomy bridge、direct fallback、root discovery
- R8-33、R8-34、R8-35 SEO/GEO 兼容回归
- #854、#857 持久账本兼容回归
- SEO #816 audit isolation 与 UI audit
- Python compileall

已知旧测试 `test_r8_15_ui_truth.py` 仍硬编码要求 `phase: "R8-15"`，与当前 R8-24/#860 页面身份不符；该失败为过时 UI 契约，不是本补丁功能回归。会由 Windows CI 的当前构建契约给出最终构建结论。

## 6. 真实生产验收状态

在候选安装前没有修改运行中的 #860，也没有手动发布或提交。因此本报告当前真实结果仍为：

- 新公网 URL：0
- 新搜索提交：0
- 实际抓取/收录：0
- 搜索曝光/点击：未新增证据

安装候选后，原调度器可重新判定该 Asset；只有 Remote Agent 上传成功且公网 HTTP、内容、canonical、Schema 和 indexability 验证全部通过才记为 `PUBLISHED`。只有搜索平台端点返回可核验接受回执才记为 `SUBMITTED`。收录仍需后续 Search Console/抓取证据，不能由提交推定。

## 7. 回滚与数据保护

覆盖安装前备份既有数据目录。回滚到 #860 程序文件不会删除 Asset、Opportunity、Revision 或历史 Receipt；本补丁没有数据迁移和批量重写。若生产部署失败，资产保持 `QC_PASSED` 或记录明确失败原因，不伪造成功，也不重复发布。
