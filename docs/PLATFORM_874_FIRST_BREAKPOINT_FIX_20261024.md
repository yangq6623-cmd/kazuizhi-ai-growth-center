# 卡嘴子 #874 第一断点定位与精准修复报告

日期：2026-10-24  
现场基线：Build #874，运行标识 R8-24 / 3a030cd1  
业务身份：MISSION-20260924-DF7DB2 / CMD-20261019-073EED / PLAN-D37B40F356

## 维修前只读证据

| 项目 | 原始证据 | 结论 |
| --- | --- | --- |
| R7 UI Snapshot | 同一只读接口连续耗时 4936、1773、5994、2714、6541 ms；返回约 470 KB、完整账本 1408 条、展示窗口 200 条 | 后台任务正常；读取路径仍进入进程级 JSON 写锁，前端失败后没有明确的最后成功快照时间 |
| GEO 49/50 | fast-ui 从最近 1000 条 Receipt 计算为 49/50；完整 evidence-compact 从全账本计算为 50/50 | 统计截断缺陷，不是 Evidence 丢失 |
| 差异 Evidence | GEO50-D02 / GEO-RECEIPT-08F460F93A2C / doubao_web / 2026-10-01 23:32:15 +08:00 | 有效 A 级历史证据被最近 1000 条窗口排除 |
| GEO 历史任务 | 95EE、FEF4、6EBC、8042 及新增 50F7 均有一次 RUNNING Attempt、无匹配 Receipt，随后出现 STALE_LEASE_RECOVERED/requeued | 通用恢复器错误读取顶层 heartbeat，忽略嵌套 lease.heartbeat_at，把可能已发送的浏览器任务放回 queued |
| GEO 新任务 | 浏览器代理五平台 ready；最近真实结果 2026-10-24 00:53:29 +08:00 | 历史阻塞没有完全饿死新合法任务 |
| SEO 35/34 | 唯一未提交 Asset SEO-50AAE9309BF1，公网 URL https://kazuizhi.com/seo/dd4c10f8a0e9a48b/，部署 Receipt 存在；提交阻塞 publication_scope_not_approved | 正常权限等待，不强制提交，不改代码 |
| 外部社媒 0 | 发布准备：24 个授权身份、13 已连接、11 待 PC 扫码、PC 会话 0；真实 URL/Post ID 0 | 第一断点是账号/会话授权，不是发布代码；未执行外发 |
| GSC | 报告更新到 2026-10-16：已索引 31、未索引 13；www 根首页旧 404 当前已可正常打开并进入首页 | 历史报告有延迟；不据此直接改生产网站 |
| 稳定性 | #874 守护启动于 2026-10-23 20:35:05 +08:00；检查时不足 24 小时 | #874 独立 24 小时/7 天尚未通过 |

## 已确认代码缺陷与最小修复

1. R7 owner snapshot 使用 read_json_snapshot 读取只读账本，不再等待进程级写锁；临时原子替换异常时返回带 snapshot_state=cached、原 generated_at 和 served_at 的最后成功快照。
2. R7 前端刷新失败时保留既有数字并明确显示最后成功快照时间，不把超时解释为后台停止，也不显示伪造的零。
3. GEO fast snapshot 的固定 50 问正式矩阵从完整 Receipt Ledger 计算；最近 1000 条窗口仅用于紧凑的近期辅助数据。
4. 通用恢复器不再重新排队浏览器外部动作。未过期的嵌套 lease 保持 running；过期且有唯一精准 Receipt 的本地关联为 succeeded；无 Receipt 或歧义的进入 authorization_required/UNCERTAIN 并禁止重放。云端 API 原有有界恢复保持不变。

## 明确保留不动

- 五条历史任务不补造 Receipt、不重新发送、不清空；现有生产记录仍由精准只读对账决定。
- SEO-50AAE9309BF1 不越过 publication_scope_not_approved。
- 社媒账号不代替用户扫码，不发送测试内容。
- Mission、Command、Plan、SEO/GEO 历史账本、订单、资金、用户、小程序和师傅端均不修改。
- GSC 的 SUBMITTED、INDEXED、历史报告更新时间继续分开统计。

## 验收边界

本次自动化测试仅使用临时 LOCALAPPDATA 和合成账本，不访问生产账号，不产生外部请求。CI/安装器通过只代表候选代码与 Windows 包通过；#874 后继候选的本机覆盖安装、真实生产回执、24 小时及 7 天自然运行必须另行现场验收。
