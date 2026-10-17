# #811 GEO Evidence 双接口超时：集中修复与交付门禁（2026-10-17）

## 背景
#810（188fa27b）现场间歇出现 `/api/r8-25/phase1-acceptance` 15 秒超时、`/api/r8-24/geo-growth/evidence-compact` 20 秒超时。重复刷新后可间歇显示 4/4。Chrome 扩展 `connected=true`、5/5 平台 ready。807 条历史队列：10 条 `cloud_auto/api` 排队、73 条历史技术阻塞；二者与 Evidence HTTP 超时是不同问题。

## 根因假设和代码核对
后端已使用 ThreadingHTTPServer；Evidence 采用后台缓存，验收账本/守护状态使用无锁快照读，原有锁保护并非唯一根因。实际前端 `build_info.js` 所安装的全局 FetchBudget 仅允许两个同源 API 请求同时执行，且 GEO 两个只读查询使用默认优先级，可能在其他慢查询之后排队直到各自 AbortController 15/20 秒超时。原 `geo-growth-os.js` 还在 Evidence 请求启动时并行启动 phase-1 请求，放大拥塞。该推断须经过 Windows 现场请求计时验证；不能宣称已100%确定原因。

## 修复内容
1. `web/build_info.js`：仅豁免明确路径的两个 **GET** 快照接口，其他 API / POST / 写入仍接受双槽总线限制。
2. `web/geo-growth-os.js`：Evidence 请求结束后再发 phase-1 GET；phase-1 单飞且 90 秒内至多发起一次；保留超时与历史 A/B 证据隔离。未提高客户端超时上限。
3. 不修改真实任务队列，不批量重发 73 条旧题，不将 10 条 cloud_auto/API 排队任务伪装成浏览器执行。
4. 已有慢请求诊断：`/api/r8-24/geo-growth/http-health`、`evidence-health`、`fast-health`。验收时需要结合它们判断服务端是否真有请求执行。

## 本地已执行
- `node --check`：更新后的两个 JS 文件通过。
- 单次 UI 模拟 100 轮 Evidence 强制刷新：两条慢 API 占满全局两槽时，Evidence 仍能及时发出；phase-1 不并发，未反复触发。
- 本地未执行完整 Windows 原生服务；不能据此宣布现场稳定。

## Windows 验收门禁
- `node 04_Build/v2/test_geo_811_fetch_budget.cjs`：100 轮队列拥塞回归。
- `python 04_Build/v2/test_geo_811_http_concurrency.py`：模拟共享 JSON 写锁占用和 Evidence 后台读阻塞时，两个 API 共 200 次真实 HTTP 请求必须返回有效 JSON，且不得制造 A/B 成绩。
- `python 04_Build/v2/test_r8_29_geo_evidence_lockfree.py` 与已有 GEO/R8、Windows 安装包、冷启动回归必须全部通过。
- 现场 Chrome 真实环境进一步检查 HTTP 慢请求和 15/20 秒间歇超时；连续刷新、重启保持证据无损，新任务端到端 Receipt 为单独业务验收，不能用 50/50 历史证据代替。

## 交付限制
CI 未全绿或现场请求仍间歇超时：不交付为“最终修复”。优先收集 http-health 的 slow/inflight 信息，不能只增加超时秒数。保留 #810 可回滚安装包，先建单独 PR，不直合并 main、不修改生产服务器。
