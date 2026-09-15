# AI自动化交接文档归档

## 当前正式交接基线（按接手顺序）

1. `V1.9.5_ENTERPRISE_R3_FULL_WINDOW_HANDOFF_20260915.md`
   - 当前最完整的“本窗口总交接文档”GitHub 归档版。
   - 已按时间、问题点、根因、修复、关键路径、构建链、剩余待办、回滚规则、下一窗口接手顺序整理。
   - 新窗口或新开发者接手时优先打开这一份，目标是“一眼望到头”。

2. `V1.9.5_ENTERPRISE_R3_HANDOFF_20260915.md`
   - R3 核心安装、构建、Dashboard、端口、回滚、后续升级规则的技术交接版。

3. 根目录状态文件
   - `VERSION`
   - `CHANGELOG.md`
   - `V1.9.5_BUILD_STATUS.md`

> 同内容的中文 DOCX 下载版已在交接聊天中生成，GitHub 仓库以完整 Markdown 版本作为长期可检索、可 diff、可维护的正式归档，避免二进制文件损坏影响后续接手。

## 当前稳定基线

- 产品版本：`V1.9.5.3 Enterprise R3`
- 稳定代码基线：`31b5f2ee45fd1abc91210f6fdb851ab7ed811263`
- 成功 GitHub Actions：`Run #65 / ID 34965930117`
- R3 运行端口：`8876`
- 基线保护分支：`baseline/v1.9.5-enterprise-r3-20260915`

## 历史交接资料

已收到 AI自动化交接文档(1).zip。

包含版本资料：

- Kazuizhi_AI_V1.8.4_Handoff.docx
- Kazuizhi_AI_V1.8.5_Handoff.docx
- Kazuizhi_AI_V1.8.5_Handoff (1).docx
- 卡嘴子_AI增长运营中心_V1.8.2_交接文档_自主学习与30天增长案例基线版.docx
- 卡嘴子_AI增长运营中心_V1.8.3_交接文档_AI云端自动同步桥版.docx
- 卡嘴子_AI增长运营中心_本窗口总交接文档_截至V1.8.1_20260914.docx

用途：
- V1.8.x 资料作为历史基线与回溯资料；
- V1.9.5 Enterprise R3 文档作为当前继续开发和升级的主要基线。

## 维护规则

每个可用重大版本完成后，必须：
1. 新增或更新“本窗口总交接”文档；
2. 更新本索引；
3. 更新根目录 `VERSION`、`CHANGELOG.md`、`V1.9.5_BUILD_STATUS.md`；
4. 保留成功 GitHub Actions Run、关键 commit 和安装包 Artifact 信息；
5. 为稳定版本保留可回退分支或 tag；
6. 不允许只保存在聊天记录中。
