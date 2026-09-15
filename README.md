# 卡嘴子 AI 增长运营中心

项目：Kazuizhi AI Growth Center

当前正式开发基线：**V1.9.5 Enterprise R3**
基础版本：V1.8.5

目标：建立可持续升级的 AI 经营分析平台。

## 当前状态

R3 已解决 Windows Enterprise 安装包、新版 Dashboard 资源打包和旧页面反复加载的核心问题。

已验证：
- GitHub Actions Windows 构建成功
- PyInstaller Enterprise Dashboard 打包成功
- Inno Setup Installer 生成成功
- 新版运营驾驶舱可正常启动
- R3 使用独立安装身份/目录与独立本地端口 8876

详细交接文档：

`docs/V1.9.5_ENTERPRISE_R3_HANDOFF_20260915.md`

## V1.9.5 / R3 功能方向

- AI 经营驾驶舱
- KPI 数据看板
- 增长分析中心
- SEO/GEO 中心
- AI 任务中心
- 自动化调度
- 数据中心
- 系统健康与日志告警
- 月度经营报告
- 版本管理与回滚体系

## 后续重点

- 统一 R3 前端版本文字和端口显示
- 清理重复菜单
- 接入真实订单、用户、师傅、团长、收入等业务数据
- 接入 SEO/GEO 数据
- 完善 AI 自动化任务执行与告警
- 正式发布前隐藏 console 窗口并保留日志能力

## 安全原则

AI 负责分析、报告、建议。
资金相关操作保持人工控制。

## 升级规则

后续重大升级必须同步更新：
- `docs/V1.9.5_ENTERPRISE_R3_HANDOFF_20260915.md`
- `CHANGELOG.md`
- `VERSION`
- `V1.9.5_BUILD_STATUS.md`

禁止只依赖聊天记录作为版本交接依据。
