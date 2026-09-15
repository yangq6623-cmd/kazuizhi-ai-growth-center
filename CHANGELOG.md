# V2.0.0 Beta — 2026-09-15

Independent V2 source/spec/installer workflow; unified runtime and frontend identity; actual Setup artifact; automated install/reinstall/uninstall and R3 preservation checks. Historical AI feature recovery remains pending.

# CHANGELOG

## V1.9.5 Enterprise R3 — 2026-09-15

### 已完成
- 修复新安装包仍加载旧 Dashboard 的问题。
- Enterprise Dashboard 改为独立前端资源基线。
- PyInstaller spec 固定打包 Enterprise 前端资源到 `_internal/web`。
- GitHub Actions 增加打包前/打包后前端校验。
- 构建前清理 `build/`、`dist/`、`installer_output/`，避免旧产物污染。
- 修复 Inno Setup 已生成但 `build_installer.ps1` 误判失败的问题。
- Inno Setup 安装前强制清理旧 `_internal/web`。
- R3 使用独立 AppId、独立安装目录和独立快捷方式。
- R3 本地运行端口调整为 `8876`，与旧版 `8765` 隔离。
- 新版“卡嘴子 AI 增长运营中心 / 运营驾驶舱”已成功显示。
- GitHub Actions R3 Build #65 构建成功。

### 当前 Dashboard 已包含
- KPI 数据看板
- 业务数据趋势
- 增长分析中心
- SEO/GEO 中心
- AI 任务中心
- 自动化调度
- 系统健康/服务监控
- 今日任务/最新动态
- AI 运营建议
- 快捷操作

### 待处理
- 统一部分前端 `R2` 文案为 `R3`。
- 统一 Dashboard 端口显示为实际 R3 端口 `8876`。
- 清理左侧重复菜单项。
- 接真实订单、收入、用户、师傅、团长、SEO/GEO 等业务数据。
- 正式发布前评估隐藏 console 窗口并保留日志能力。

### 交接
详见：`docs/V1.9.5_ENTERPRISE_R3_HANDOFF_20260915.md`

---

## V1.9.5

新增：
- AI经营驾驶舱规划
- 月度经营报告体系
- 双增长分析模型
- 数据结构规划
- 版本管理体系

基于：V1.8.5
