# GEO 扩展 2.2.2.804 修复与交付说明

## 背景
#801 运行现场记录 `content-agent.js` 全局 `SELECTORS` 二次声明和 `chrome.runtime.onMessage` 缺失错误，Chrome popup 另出现 `page_load_timeout`。扩展版本为 2.2.2.803，基线 Commit `287c27102a7048dc292c2aa120c72e66d764be9a`。

## 目标
只修复 GEO Chrome 扩展双注入、消息监听与页面加载判定，不扩大到 #801 本地后端。

## 文件结构
- `05_V2.0.0_Source/browser_extension/kazuizhi_geo/manifest.json`: 版本 2.2.2.804
- `content-agent.js`: 在隔离闭包中注册并设置同页面幂等锁
- `service-worker.js`: 仅在明确无消息接收端时再注入；提前接受已交互 DOM
- `04_Build/v2/test_geo_extension_804.js`: 回归测试
- `.github/workflows/geo_extension_804_hotfix.yml`: 静态检查、回归测试和独立 ZIP

## 执行步骤
1. CI 检查全部扩展脚本 `node --check`，运行 `test_geo_extension_804.js`。
2. CI 成功后，从 workflow Artifacts 下载独立扩展 ZIP 并解压。
3. 在 `chrome://extensions` 停用旧扩展并用 `加载已解压的扩展程序` 选择新目录；旧版目录先保留以便回滚。
4. 安装后刷新已开的豆包、抖音、DeepSeek、千问和 360/纳米 AI 标签页。
5. 只对一个有授权且已登录的平台做单条真实性验证，核对外部网页 URL、原始回答、引用 URL 和真实 Receipt。
6. 再独立检查本地 #801 `/api/r8-25/phase1-acceptance`，该后端接口未在此补丁中修改。

## 限制
不得伪造 Evidence，不把 `ready`、`SUBMITTED`、旧 50/50 历史快照当成正式通过；不得触碰 #801 数据、支付、小程序、师傅端。

## 验收标准
- `node --check` 全部通过，回归测试通过，产生独立扩展 ZIP。
- 重复注入不再次声明 SELECTORS，消息无接收端仅触发一次补注入。
- Chrome 五平台真实登录及回答采集仍需在用户本机实测；此项不能由 CI 替代。

## 完成交付
GitHub 独立修复分支、CI 工作流日志、独立扩展 ZIP Artifact、问题和回滚说明。
