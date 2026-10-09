# 卡嘴子 SEO/GEO 浏览器预览

本目录提供 UI 验收，不需要下载 Windows EXE。

- `preview/index.html` 为统一浏览器入口。使用真实 SEO 前端 HTML 与真实 GEO Growth OS JS，静态样例模拟 API。
- 不连接 localhost/127.0.0.1、本地模型、公网发布器及任何真实服务端接口。
- 任何写入/授权/真实回执在预览中均被模拟或阻止。**禁止输入密码、令牌、客户隐私。**
- 样例业务数字不是正式业务回执；SEO 索引和 GEO A/B 的样例计数不作为验收证明。
- GitHub Pages 启用后建议固定入口： `https://yangq6623-cmd.github.io/kazuizhi-ai-growth-center/preview/`
- 未启用 Pages 时，临时使用 raw.githack 开发链接；该服务可能要求一次安全确认，缓存更新可能滞后数分钟。
- 主干每次修复后，需将真实前端源码改动同步至本预览分支；入口会即时读取该分支上的 `05_V2.0.0_Source/web/r8_13_seo_geo.html` 与 `geo-growth-os.js`。
- 真正的后端修复仍需 Windows/测试环境、外部 AI 或站长平台的授权回执验证。

本次基线：#761 (`86b5f755c6ac9fcaf0813189f46096183820c578`)。
