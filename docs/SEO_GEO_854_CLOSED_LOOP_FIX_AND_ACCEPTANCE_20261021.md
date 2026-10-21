# 卡嘴子 #854 SEO/GEO 自动化执行闭环集中修复与验收说明

日期：2026-10-21  
基线：`b9c55b62ce3bbc9487900aea05f9dcde772c37bb`（本机已安装 #854）  
修复分支：`codex/854-seo-geo-closed-loop-fix`

## 1. 范围与安全边界

本次只在现有 R7/R8、Mission、Command、Controller Plan、Task、Receipt、SEO Asset 和 GEO Evidence 架构上增量修复。没有创建新 Mission，没有清理或重写历史 Task/Receipt/Evidence，没有重发 73/78 条历史超时或 81 条发送状态不确定记录，没有执行公网发布、外部 AI 发送、资金、订单或账号授权操作。

## 2. #854 修复前现场证据

- 当前 Mission：`MISSION-20260924-DF7DB2`；Command：`CMD-20261019-073EED`；Plan：`PLAN-D37B40F356`。
- 2026-10-21 上午老板总控显示 `181/200`、队列 19、运行 0、失败 0。181+19 恰好等于 200，但 R7 持久账本实际已超过 200 条。
- SEO 累计真实状态为公网 URL 32、搜索提交 31；这些数字不等于收录或获客。
- GEO 正式基线 50/50；运营机会 13；正式 Evidence 最近一条为 `GEO-RECEIPT-F2492A43B73F`，Qwen，时间 `2026-10-20T14:24:31.614Z`。这证明正式外部回执并非停在 10 月 19 日，但主动推荐和官网引用仍没有新增证据。
- GEO 队列显示 2、运行 0、待核查 78。浏览器代理在线，但最近领取为 `queue_empty`；平台级 24 小时冷却示例的阻塞任务为 `GEO-TASK-FEF4F799B1B1`，现场下一次允许时间为 `2026-10-21T14:27:14Z`。
- `/api/r8-24/geo-growth/fast-ui` 的快照代码只复制队列总数，没有复制完整接口已经计算出的 `routing_diagnostics` 和 `blockage_diagnostics`。因此高级页面的“队列路由”为空、待核查分类为“未知”，不能据此判断真实队列为空。
- 火山方舟页面当时筛选 `2026-10-05` 至 `2026-10-18`：773 次调用、总 Token 39.7 万（输入 9.1 万、输出 30.6 万）。GEO C 级 Signal 878 是当前本地账本累计量，统计窗口和数据粒度均不同，不能直接对等。尝试刷新同窗口时账号会话已退出，因此尚缺同一时间范围的云端费用/调用原始证据。

## 3. 根因

### 3.1 Mission 200/200

`core/r7_engine.py::list_jobs()` 固定只返回最近 200 条。Mission 汇总和总控指标直接对这 200 条计数，把“列表窗口”误当成“账本容量”。新一天的 20 条任务进入窗口后，旧任务被挤出，页面便出现 180/200、181/200 等变化；这不是历史任务丢失，也不是 Mission 只能执行 200 项。

### 3.2 当天完成一轮后没有可靠续轮

旧机制每天生成固定 20 条基础排班，但没有一个基于真实 SEO Asset、到期 GEO Schedule 和结果差异的同日批次物化器。部分普通 SEO/GEO 排班还会反复生成同一个通用本地草稿，任务完成数增长却不代表新增 Asset、公网页面或 Evidence。

### 3.3 GEO 两条排队任务看似无人领取

队列的执行器路由依赖 `provider + test_method + expected_platform`。Chrome 只能领取匹配平台的 browser 任务，不能代领 `cloud_auto/api`；历史发送状态不确定的任务也不能重发。快速快照遗漏路由与阻塞详情，使页面无法显示两条任务各自允许的执行器、退避或授权原因，造成 `queue_empty` 与“队列 2”看似矛盾。

### 3.4 SEO QC 0 缺少可追溯原因

本地 QC 失败原因过去只存在于一次运行返回值，没有写回 Asset。页面只能看到 GENERATED/QC 0，无法区分排程等待与质量拒绝。

## 4. 实际修改

| 文件 | 最小修改 |
|---|---|
| `core/r7_engine.py` | 保留默认最近 200 条显示窗口，新增显式分页和完整账本计数；引擎状态从全账本统计。 |
| `core/mission_ledger.py`、`core/r8_22_autonomous_convergence.py` | Mission 进度读取完整 R7 账本；分开本地完成、草稿、Asset、公网、SUBMITTED、抓取/收录与正式 GEO Evidence。 |
| `core/daily_workforce.py` | 基础排班标记 B01；上一批完成后，仅在发现既有待推进 SEO Asset 或已到期 GEO Schedule 时创建 B02/B03…；批次幂等，沿用原 Mission/Command。 |
| `core/autonomy.py` | 新增 `seo_pipeline` 和 `geo_growth_cycle`，复用现有工作器；普通每日 SEO/GEO 排班停止制造重复通用草稿。 |
| `core/geo_validation.py` | 输出每条 queued Task 的 Task ID、路由、允许执行器、等待原因和关联 ID；新任务入队后唤醒原执行器，保留轮询、授权、冷却和幂等门槛。 |
| `core/geo_autonomy.py` | 执行器支持入队事件即时唤醒；未取消任何冷却或不确定结果隔离。 |
| `backend/r8_20_seo_geo_growth_patch.py` | fast-ui 快照补回路由与阻塞诊断，避免缓存概览把未知显示成空。 |
| `core/seo_geo_growth.py`、`core/seo_geo_autonomy.py` | QC 失败原因、次数和检查时间写回原 Asset；失败仍保持 GENERATED，绝不伪装 QC 通过。 |
| `web/geo-growth-os.js` | 显示 queued Task ID、provider/method/platform、允许执行器、路由状态和等待原因。 |
| `web/r8_13_seo_geo.html` | 显示 Asset ID、Revision 与 QC 拒绝原因。 |
| `web/r8_22_autonomy.js` | 明示完整账本与 200 条列表窗口的区别，显示 Batch ID 和下一次到期唤醒。 |

## 5. 隔离测试结果

新增 `04_Build/v2/test_854_closed_loop_concentration.py`，使用临时数据目录验证：

- B01 完成后能生成同 Mission/Command 的 B02；B02 完成且出现新资格条件后可生成 B03。
- 相同资格指纹不会重复创建批次、Mission、内容或外部动作。
- 超过 200 条时默认列表仍只返回 200 条，但 Mission 汇总覆盖完整账本。
- GEO cloud API 与五平台 browser 路由严格分离；不确定发送状态继续隔离。
- 新任务入队会唤醒原工作器，但实际领取仍服从授权、冷却和 provider 匹配。
- SEO QC 失败原因持久化且不会推进到 QC_PASSED。
- 固定日排班不再创建重复通用 SEO 草稿。

本地已通过的定向/兼容回归包括：R7 Block A/B、daily workforce、R8-22、#836 Command/Mission、#840 owner SEO、#841 SEO 内容质量、R8-13/14/15、R8-34/36/37、GEO #808/#809/#812/#816/#818、R8-23 工作台、R8-24 fast-ui/Evidence fail-safe，以及修改文件 Python/JavaScript/HTML 内联脚本语法检查。

两个旧回归门槛本身落后于现有基线，已只修正测试兼容范围：R8-19 可见版本列表补充 R8-24/R8-25；GEO 主工作区测试同时接受 #853 已采用的直接核心挂载方式，不要求恢复曾导致空白的嵌套 GEO iframe。

## 6. 当前可确认与尚未通过

### 已确认

1. 200/200 的统计根因已定位并在源码中修复；完整账本不会再被 200 条 UI 窗口截断。
2. 同日第二、第三轮的控制逻辑已通过隔离测试；无合格工作时会等待，不生成凑数任务。
3. GEO 快照丢失路由诊断的代码缺陷已修复；安装候选后可直接看到两条排队任务的真实 Task ID 与执行器/等待原因。
4. SEO 任务完成、公网 URL、SUBMITTED、抓取/收录和经营转化已经在指标上分离。
5. 原有 50/50、历史 Receipt/Evidence、73/78 条历史超时/待核查和 81 条不确定发送保护没有被取消。

### 尚未宣称通过

1. 本分支尚未安装到用户现场前，不能声称 #854 现场两条排队任务已被新诊断界面解开；修复前 fast-ui 没有暴露它们的 Task ID，不能凭猜测填写。
2. 没有在本次诊断中执行真实外部 AI 发送。真实发送属于对外动作，且现场存在冷却/路由/登录条件；必须在安装后看到精确 Task 和资格条件，再按动作时确认执行。没有新 Evidence 就不宣称 GEO 端到端已打通。
3. 24 小时连续运行尚未实际经过，不能宣称 24 小时无人值守验收通过。
4. 火山方舟账号会话已退出，878 Signal 与云端 API 的同窗口调用量、Token 和费用仍缺用户重新登录后的只读证据。
5. 搜索抓取、收录和获客目前没有新增真实证据；32 个公网 URL 与 31 条 SUBMITTED 不等于收录或转化。

## 7. 安装、兼容与回滚

- Windows CI 必须完成源码回归、全 JavaScript 检查、打包、Defender 检查、静默安装、启动、覆盖升级、持久数据保留和卸载测试后，候选才可交付。
- 安装包沿用现有数据目录和 R7/R8 JSON 账本，不执行数据库迁移或初始化覆盖。
- 回滚使用安装测试生成的升级前备份恢复程序文件；持久数据目录不随卸载清除。若候选安装后未通过现场 GEO 路由/SEO 对账，应恢复 #854 程序版本并保留候选运行期间新产生的原始账本，禁止用旧备份覆盖新 Receipt。
- 最终 Commit、GitHub Actions Run、安装包 SHA256 以随包 `BUILD_RECORD.json` 和 `SHA256SUMS.txt` 为准。

## 8. 老板结论

- **200/200：** 是统计窗口缺陷，不是执行上限；源码已修复。
- **同日续轮：** 有真实合格工作即可 B02/B03 继续；没有就等待下一真实结果/到期时间。
- **过去 200 项：** 不能再用任务完成数回答“发布了什么”。现场真实成果仍应单列为 SEO 公网 32、搜索提交 31、正式 GEO Evidence 50；其余本地草稿/分析由新版本完整账本结果分类展示。
- **GEO 队列 2：** 修复前证据只足以证明诊断字段丢失与严格路由存在，不足以安全猜测两个 Task ID 或强制 Chrome 重发；候选安装后会显示逐条原始路由。
- **新真实外部 AI 回执：** 本次未制造；修复前已核实最近真实正式回执为 `GEO-RECEIPT-F2492A43B73F`。
- **SEO 增量：** 本次没有手动发布，仍为公网 32、SUBMITTED 31；QC 等待原因将在候选中可追溯。
- **24 小时自动运行：** 控制链缺陷已补强并通过隔离测试，但真实 24 小时观察和新外部 Evidence 仍是安装后的现场验收项。
