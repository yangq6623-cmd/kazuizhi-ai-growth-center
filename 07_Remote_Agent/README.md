# R8-17 Remote Agent

目标：完整 AI 自动运营中心运行在老板电脑；生产服务器只保留低内存、无 UI 的固定执行层。后续桌面端升级不应要求重复修改生产服务器。

## 固定边界

- 桌面端：ChatGPT/AI 决策、8 个员工、SEO/GEO、内容生产、素材、数据分析、搜索平台提交与回执编排。
- 服务器端：静态公网文件发布、SHA-256 校验、发布前备份、回滚、真实执行回执。
- 不在服务器运行完整 AI 控制台、浏览器自动化、模型、图片/视频生成。
- 不公开 `127.0.0.1:8876`，不提供公网管理 UI。

## 协议

长期固定协议名：`kz-remote-agent-v1`。

生产安装目标为 IIS 子应用 `/kz-agent`，复用现有 `kazuizhi.com` HTTPS 证书和 443 端口。所有请求必须使用设备 key、时间戳、nonce、body SHA-256 与 HMAC-SHA256 签名；5 分钟时钟窗口并拒绝 nonce 重放。

服务器只允许静态公开文件类型，明确拒绝 `Web.config`、ASP.NET/PHP/PowerShell/EXE/DLL 等服务器代码或配置写入，不提供任意 shell/命令执行能力。

## 一次性部署目标

- Windows Server 2012 R2 / IIS 兼容。
- 独立 IIS AppPool，按需启动，低资源占用。
- DPAPI LocalMachine 加密保存长期共享密钥。
- 分块上传，单文件可扩展到 512 MB。
- 发布前备份、失败不推进真值状态、支持 rollback。
- durable receipt：桌面端只依据真实服务器回执推进 PUBLISHED。
- 桌面后续 #700/#1000/R9/R10 继续复用 v1；只有协议新增能力时才增加 v2，不破坏 v1。

## 成本原则

Remote Agent 本身不引入新的订阅服务；复用现有服务器、域名、IIS 和 HTTPS。现有服务器/域名/流量费用仍按原计划存在；未来任何付费第三方模型/API/广告渠道费用独立计算。
