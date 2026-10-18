# GEO #816 专项现场执行反馈（2026-10-18）

## 结论与验收状态

**部分完成，尚未通过真实网页 Receipt 验收。不得据此宣称现场已修好或 GEO 已形成闭环。**

已连接用户本机 Chrome 的 extension 浏览器，实际读取 `http://127.0.0.1:8876/` #816 工作台。没有使用云端浏览器替代本机。此会话具备本机 Chrome 网页操作能力；没有证明具有 Windows 桌面、进程、磁盘文件、扩展后台 service worker 或本机命令行操作能力。容器终端是独立 Linux 工作区，不能当作用户 Windows。

独立分支：`codex/r8-28-geo-816-field-repair-20261018`。基线：`540ff6bde9296b1ca63f4d63f26f070464a131da`，即 #816 当前界面提交。没有覆盖安装、重启或暂停 SEO，没有批量重试任何历史 GEO 任务，没有重置 Evidence 或扩展安全标记。

## 现场读取与限制

- Chrome 返回实际标签页：本机 #816 工作台、GitHub #816 Actions、千问、DeepSeek、抖音、豆包、纳米 AI 和扩展管理页。
- 本机工作台显示 R8-24 / #816 / commit 540ff6bd。
- GEO 正式矩阵 50/50、Evidence 50、完整证据 50/50；各平台 10/10。
- 排队 10，执行中 0，待授权 73。
- 运营 Signal 701，机会 13，等待复测 13，闭环完成 0。
- 运营复测显示 24h 0/0、72h 0/0、7d 0/0。
- 正式旁路复测显示 24h 2/50、72h 2/50、7d 1/7；与运营复测是不同统计，不能混算。
- 现场领取记录：`2026-10-18T11:24:13+08:00`，`so360_ai_search`，`queue_empty`，无 Task ID；后续页面显示 `11:27:14+08:00` 同样结果。
- 浏览器代理在线、国内平台 5/5、`global_retest_cooldown`、最近真实回执“尚无”。这只是页面状态，不能替代成功 Receipt。
- 最近可见历史 Receipt：`GEO-RECEIPT-B06C42C2D7E6`，doubao_web，2026-10-16T19:29:16.770Z，问题“卡嘴子能不能找家电维修师傅？”。没有将其计为本次新增执行。
- 点击“诊断读取”：后端证据缓存就绪，3397898 字节、4 分区、读取线程 0、无记录错误；主快照就绪。这说明快照可读，不证明业务队列推进。
- 控制台可见多条 `A listener indicated an asynchronous response ... message channel closed`，发生于工作台及嵌入页。来源未定位，不能据此直接判为 GEO 扩展根因。
- Chrome 内部扩展管理标签页不能被此浏览器工具接管，故用户提供的 GEO 扩展版本 2.2.2.814 未从扩展管理页独立核实。
- 尝试打开源码中明确存在的只读队列接口 `/api/r8-19/geo/queue`，Chrome 返回 `net::ERR_BLOCKED_BY_CLIENT`。没有改用其他通道绕过此限制。当前 UI 没有展示 73 条历史记录详情，因此没有取得逐条日志和真实队列分类数量。

## 根因：已确认代码事实与现场推断分开

### A. 监测周期确实存在阻塞运营复测的代码路径（已修复，待部署）

`core/geo_autonomy.py:run_once` 在 50 问目标完成后，进入 `waiting_next_monitor_cycle` 并提前返回，位于 `geo_cloud_executor.run_once` 之前。`geo_growth_orchestrator._ensure_retest_task` 却把运营 24h/72h/7d 复测写入同一 `cloud_auto/api` 队列。结果是基线监测休眠能够阻止独立运营复测的执行。

修复：在基线周期判断前，仅调度已经排队、明确属于三个运营复测 Mission、provider=cloud_auto、method=api、未绑定网页平台、退避时间已到的任务。每轮至多一次。没有创建新复测、没有重放失败/待授权任务，没有修改正式 A/B Evidence。

同时为 cloud executor 加可选 Task ID 范围，并对实际 claim 添加精确白名单，防止队列变化后领取范围外任务。默认调用兼容原逻辑。

这是可复现的源码缺陷；由于现场队列详情读取受阻，尚不能断言现场 10 条全部由此造成。

### B. 运营复测 0/0 存在确定的显示缺陷（已修复，待部署）

`backend/r8_20_seo_geo_growth_patch.py:_geo_fast_ui_compact` 丢弃 `retest_windows`，前端以空对象将缺失值渲染为 0/0。修复为只携带三个窗口的 scheduled/queued/completed 数值，维持精简响应，不引入大账本读取。

这能解释统计显示错误，但不能证明 13 个机会均已产生有效到期计划或已执行。页面中的 SUBMITTED 也不等同于真实发布；部分机会为 SUBMITTED，至少一条为 PUBLISHED。不能把 13 个机会算作 13 条本次新增发布或曝光。

### C. 五平台在线与 queue_empty 并不矛盾（现场任务构成待核实）

Chrome claim 只领取对应平台、browser 方法且从未尝试的任务；总排队数包含 API 或其他路由。在线心跳不会使 cloud_auto/api 自动成为网页任务。源码另有全局 24h 新建浏览器复测限制，现场已显示 global_retest_cooldown。该保护未放宽或清空。

现有 one-shot canary 限于豆包固定 10 问中的从未尝试题；50/50 完成后，不应假设一定存在新题。此次未调用可能领取历史问题的人工准备按钮，未伪造新题或绕开安全标记。

### D. 73 条不能统称真实授权障碍（增加可见分类，待部署）

源码已有只读分类 `legacy_technical_requires_review`、`real_authorization_or_risk_control`、`unclassified_requires_review`，旧 UI 却统称“待授权 / 仅真实阻塞”。改成“待授权 / 待核查”，显示队列路由和上述分类。

另增加“不确定发送记录”只读计数：明确 uncertain 标记或超时记录均保守计入，可与技术/授权分类重叠。超时不是未发送证明，绝不据此重试。

**本次未获得 73 条的逐条分类、Task ID 和真实数量分布；这些仍是现场待办，不能填写估计值。**

## 修改文件

- `05_V2.0.0_Source/core/geo_autonomy.py`：运营复测独立于基线周期调度。
- `05_V2.0.0_Source/core/geo_validation.py`：claim 范围约束、只读不确定记录计数。
- `05_V2.0.0_Source/integrations/geo_cloud_executor.py`：按指定 Task IDs 执行。
- `05_V2.0.0_Source/backend/r8_20_seo_geo_growth_patch.py`：精简快照保留三个复测窗口。
- `05_V2.0.0_Source/web/geo-growth-os.js`：显示路由、阻塞分类，纠正“仅真实阻塞”文案。
- `04_Build/v2/test_geo_816_operating_retest.py`：隔离回归测试。
- `.github/workflows/build_v2_enterprise_beta.yml`：在 Windows 构建前加入新回归门禁。

## 内部测试

以下测试在独立 Linux 源码工作区通过，均不代表真实外部 AI 验收：

1. 新增测试 4/4：三个窗口越过基线冷却；失败/授权/浏览器/退避/普通基线任务保持不执行；精确 claim 不消费无关队列；精简响应保留窗口计数。
2. `test_geo_809_queue_routing.py` 通过。
3. `test_geo_808_browser_claim_truth.py` 通过。
4. `test_geo_812_claim_execute_receipt.py` 通过：仅隔离数据回归，非本次真实 Receipt。
5. `test_geo_815_canary_version.py` 通过。
6. `test_r8_34_geo_seo_closed_loop.py` 通过。
7. `node --check 05_V2.0.0_Source/web/geo-growth-os.js` 通过。
8. `git diff --check` 通过。

Windows 完整 CI 与安装包状态另行追加；在其通过之前不得把候选构建当作可安装正式版。

## 真实浏览器验收记录

| 项目 | 本次结果 |
|---|---|
| 新真实 Task ID | 无；未领取到经核实从未发送的安全任务 |
| 平台 | 未执行新外部提问 |
| 执行时间 | 无；上述 11:24/11:27 为现场领取状态时间 |
| 新 Receipt ID | 无 |
| 外部原始回答 | 无 |
| 后台新增 Evidence | 未取得新增证据 |
| 验收结论 | 未通过，禁止以心跳/旧 Evidence/隔离测试代替 |

## 下一步与限制

1. 等待独立分支 Windows CI 全部通过并取得构建产物；检查新统计和路由分类的 UI 输出。
2. 当前工具不能安装或操作 Windows 本机文件。由具备 Windows 文件/部署能力的执行环境在备份后部署候选包；保留 #816 回滚包与全部 GEO 数据，不覆盖或关闭 SEO 调度。
3. 在可读取本机队列日志的环境，导出10条排队记录、73条待核查记录以及13个机会的三个复测计划，逐条核对真实路由、退避、发送记录、发布时间和 Receipt 关联。不得批量重试。
4. 验证运营 API 复测独立推进并保存 C级 Signal；这与正式网页验收分开。
5. 按既有安全限制取得一条有明确未发送证明的新网页 Task。若固定矩阵已无新题，应实现独立、不改变固定50问基线的受控新题验收入口，并先测试去重、保留发送标记与 Receipt 归属。不能清空旧 one-shot 标记或修改历史任务来凑验收。
6. 真实执行：领取 → 外部 AI 网页 → 原始回答 → Receipt → 后台证据。补齐 Task ID、平台、准确时间、Receipt ID、完整结果或失败原因，之后才允许宣布现场修复完成。

## 回滚

本次仅提交候选源码，现场无安装变更。源码回滚到 #816 的 540ff6bd 即可；不需要 SQL 迁移，不应删除或回滚生产 Evidence/Receipt 账本。部署前后均需单独验收 SEO 仍在运行。

## 最终构建与同步记录

- 修复代码提交：[c7764e59dad19bccd5e4d3fbfb1ba6abb8170155](https://github.com/yangq6623-cmd/kazuizhi-ai-growth-center/commit/c7764e59dad19bccd5e4d3fbfb1ba6abb8170155)。
- Windows 构建 #817：[39093879002](https://github.com/yangq6623-cmd/kazuizhi-ai-growth-center/actions/runs/39093879002)，已完成，结论 **success**。
- 全部 Windows 测试门禁、打包、签名验证、扫描步骤、静默安装/启动/覆盖升级/卸载测试通过。安装测试发生在 CI 的 Windows runner，非用户本机。
- [#817 安装包产物](https://github.com/yangq6623-cmd/kazuizhi-ai-growth-center/actions/runs/39093879002/artifacts/12123967299)。另有 Portable 产物 12123523992、扩展 2.2.2.814 产物 12123788113。没有要求重装扩展。
- 没有在用户电脑安装 #817；当前安装仍为 #816。真实外部网页 Receipt 验收仍未完成，构建 success 不能替代该验收。
- 收尾只读检查 SEO 页面：显示“自动运行”、累计公开回执31、已提交URL30，今日URL提交8；历史异常周期106仍显示“需复核”，不宣称所有SEO历史问题已消失。未操作 SEO 开关，最后返回 GEO 页。
- Git 命令推送因容器没有 GitHub 用户名凭据失败，随后已通过 GitHub 连接器成功创建独立分支、上传8个文件并提交；已重新读取远端交接文档确认存在。此次是实际远端同步，不是仅本地 commit。
