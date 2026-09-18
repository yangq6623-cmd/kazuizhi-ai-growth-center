# AI自动化交接文档归档

## 当前 R8 接手顺序（2026-09-18 起）

1. `R8_R7_TO_R8_DECISION_LEDGER_AND_DEVICE_PLAN_20260918.md`
   - **R7 收尾后进入 R8 的当前最高优先级决策总表。**
   - 汇总“整理功能升级表”窗口中已经反复讨论并最终确认的 R8 决定，包含：R8-00~R8-08、Gate 顺序、单真机 Android/ADB、老板人工边界、资金边界、验证码/人脸/风险熔断、3060 视频工厂、真实发布回执、24h/72h/7 天归因。
   - 同时记录 2026-09-18 第一台真机实测：`M5QNU22319503960 / ETO-BD00`，Windows → ADB → 真机链路已通过。
   - 后续进入 R8 时先读本文件，已确认事项不再从零重复讨论。

2. `R8_PREVIEW_R8_00_HANDOFF_20260918.md`
   - R8 Preview / R8-00 安全底座交接。
   - 单真机限制、真实设备原则、老板确认发布、资金永久人工、验证转人工、禁止设备伪装和风控规避。

3. `R7_FINAL_USER_GUIDE.md` / `R7_FINAL_TEST_REPORT.md` / `R7_FINAL_UPGRADE_NOTES.md` / `R7_FINAL_KNOWN_ISSUES.md`
   - R7 Final 冻结基线。R8 只能在其上增加，不允许破坏已验证的 R7 任务、Memory、计划、审计、经营数据和 AI 员工底座。

## 历史正式交接基线（继续保留）

1. `V1.9.5_R3_MASTER_HANDOFF_PRODUCT_VISION_20260915.md`
   - 历史产品与架构总纲。
   - 统一记录：V1.8.5 功能回归补齐、项目核心理念、最终产品方向、主控 AI / 本地 Agent 分工、双增长、长期记忆、真实数据、安全边界、R3 技术基线、后续恢复顺序和正式发布验收标准。

2. `GITHUB_SOURCE_OF_TRUTH_AND_RELEASE_SOP_20260915.md`
   - GitHub 单一事实源与发布交付 SOP。
   - 规定源码、构建脚本、版本状态、交接文档、功能回归、稳定基线、Artifact 的统一保存与交付方式。
   - 默认由 AI 侧完成查源码、修改、构建、查 Run/Artifact、下载最终包并直接交付老板；老板不需要每次自己进入 GitHub 找包。

3. `V1.9.5_ENTERPRISE_R3_FULL_WINDOW_HANDOFF_20260915.md`
   - R3 构建/安装问题完整过程归档。

4. `V1.9.5_ENTERPRISE_R3_HANDOFF_20260915.md`
   - R3 核心安装、构建、Dashboard、端口、回滚和升级规则技术交接。

5. `V1.9.5_FUNCTION_REGRESSION_VS_V1.8.5_20260915.md`
   - V1.9.5 相对 V1.8.5 功能回归与恢复依据。

6. 根目录状态文件
   - `VERSION`
   - `CHANGELOG.md`
   - `V1.9.5_BUILD_STATUS.md`

> GitHub Markdown 是长期可检索、可 diff、可维护的正式归档。关键决定不得只保存在聊天记录中。

## 当前代码分支关系

- R7 Final：稳定冻结基线，不再直接做 R8 开发。
- R8 开发分支：`codex/v2-r8-growth-ops`。
- 当前 R8 Preview：在 R7 Final 稳定底座上增加 R8-00 安全层与 R8-01 单真机设备中心，不迁移或清空原有用户数据目录。

## 历史归档状态与缺口

### 已进入 GitHub 的核心资产
- 当前源码；
- PyInstaller / PowerShell / Inno Setup 构建脚本；
- GitHub Actions workflow；
- VERSION / CHANGELOG / BUILD_STATUS；
- R3、R7、R8 交接和产品方向；
- 稳定基线分支与构建 Artifact 定位信息。

### 仍需继续补齐的历史资产
`01_Legacy_V1.0-V1.8.5/` 尚未完整保存 V1.8.5 的全部历史源码 / Windows 发布包。历史交接资料仍可用于恢复功能定义，但后续应继续把能找回的发布包、升级器、源码/核心文件和 SHA256 补进 GitHub 历史归档。

## 已保留的历史交接资料

- Kazuizhi_AI_V1.8.4_Handoff.docx
- Kazuizhi_AI_V1.8.5_Handoff.docx
- Kazuizhi_AI_V1.8.5_Handoff (1).docx
- 卡嘴子_AI增长运营中心_V1.8.2_交接文档_自主学习与30天增长案例基线版.docx
- 卡嘴子_AI增长运营中心_V1.8.3_交接文档_AI云端自动同步桥版.docx
- 卡嘴子_AI增长运营中心_本窗口总交接文档_截至V1.8.1_20260914.docx

## 维护规则

每个可用重大版本完成后，必须：
1. 新增或更新“总交接与产品方向/决策总表”；
2. 更新本索引；
3. 更新根目录版本与构建状态文件；
4. 保留成功 GitHub Actions Run、关键 commit 和安装包 Artifact 信息；
5. 为稳定版本保留可回退分支或 tag；
6. 建立上一稳定版本 → 当前版本的功能回归清单；
7. 已接入能力不得在重构后无说明变为“待接入”；
8. 不允许关键理念、功能、失败经验、老板最终决定只保存在聊天记录中；
9. 正式版本必须同时保留：源码（怎么做出来）+ Artifact（做出来的包）+ 交接文档（为什么这样做）；
10. 每个 R8 Gate 必须分别标记：规划确认 / 已开发 / 自动测试通过 / Windows 安装通过 / 真机实测通过。
