# V2.1.0 Beta R8 Preview / R8-00 交接说明

R8 Preview 从已封版的 R7 Final 稳定底座继续升级，不覆盖 R7 的任务、Memory、计划、审计和经营数据用户目录。

## 当前阶段

- 显示版本：V2.1.0 Beta R8 Preview
- 阶段：R8-00 平台安全与单真机试点底座
- 当前策略：先完成 1 台真实 Android 手机验收，再开放第 2 台设备
- 视频发布：必须老板人工点击确认发布
- 资金事项：永久仅人工处理
- 验证码、短信、人脸或平台风险验证：自动化立即暂停并转人工
- 禁止设备、IMEI、Android ID、GPS 或 IP 风控规避伪装

## 包身份

GitHub Artifact、安装程序、桌面快捷方式、Windows 文件属性和运行后的可见界面均使用 R8 Preview 名称。界面左下角同时显示 GitHub Build 编号和提交短 SHA，避免再出现“功能已经进入 R8、安装包却仍显示 R7 Final”的混淆。

R7 Final 的兼容构建标识继续保留在底层静态资源契约中，用于保证已验证的 R7 核心和历史数据不因 R8 Preview 的包装升级而失效；R8 Preview 另有独立 runtime_build 与 phase 字段用于版本识别。
