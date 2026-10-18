# 卡嘴子 #818 GEO 真实账本一致性与安全复测修复说明
日期：2026-10-18；来源：#817 本机只读诊断（用户私人 ZIP，禁止公开原始数据）。

## 背景与真实问题
#817 真实账本：859 Task、847 Receipt、302 历史 Opportunity、当前有效机会13；
73 authorization_required 中 71 capture_failed:agent_response_timeout、
2 capture_failed:signal timed out；81 为可能已发送但未收到最终回执的重叠风险标签。
原有 24h 结果从11/12变成5/13，又在浏览器请求超时后显示0/0。
302个历史机会中大量 superseded 会退出当前活动列表；多个机会引用同一 Task/Receipt，
含失败Task仍链接Signal。C级内部运营评价不得计入正式 A/B。
SEO #817 自治在上一轮本机配置中 enabled=true、mode=autonomous，
历史正式50/50及所有已发布页面必须保留。

## 本次目标
1. 展示当前活动窗口与历史归档 C级关联两套独立指标。
2. 归档历史只按唯一 Task ID 或无Task时Signal ID计数；失败Task对应的Signal不计为
   经过成功Task核对的Receipt；需要具有同一 Task ID、C级非正式Receipt、Receipt ID/Signal ID一致才记入核对成功。
3. 对历史 authorization_required 用原因只读分类：技术超时、真实登录/风控、未知；
   原始state保留、不自动retry、不解除浏览器全局cooldown。
4. 明确保留现行24h/72h/7天到期规则；当前活动窗口不被历史累计算数覆盖，
   superseded记录不被删除，也不会自动重新发送历史问答。
5. 让fast-health超时回退使用同一缓存的真实retest_windows、归档和阻塞摘要；
   缺失字段显示待同步，不展示假0/0，前端fast-ui等待从5秒改为8秒。

## 代码结构
- core/geo_growth_orchestrator.py：_geo_task_blockage_snapshot、_retest_archive_summary；
  fast_status与status新增historical_retest和task_blockage。缓存构建在后台线程，不走HTTP请求线程。
- backend/r8_20_seo_geo_growth_patch.py：fast-ui精简字段、fast-health回退。
- web/geo-growth-os.js：分开显示历史链接去重、核对成功的 C级 Receipt、超时分类、
  当前活动24h/72h/7d进度；请求超时回退时仍显示真实缓存数值。
- 04_Build/v2/test_geo_818_ledger_safety.py：去重/失败不算成功/73超时分类/窗口排序等。
- .github/workflows/build_v2_enterprise_beta.yml：Windows CI新增门禁，继承#811～#817的SEO/GEO回归。

## 数据安全与限制
不得提交用户诊断原始ZIP、Task ID全集、Token、Cookie或私密记录到GitHub。
无SQL迁移、不清除旧数据、不修改历史Task state、Receipt、Evidence、不重新发送问答。
原#817不覆盖，待Windows CI完整通过再交付#818候选安装包。
如果 Windows CI、签名、Defender、升级/卸载/数据保留任一步失败，停止交付。
既有50/50 Evidence不变，C级去重只代表账本关联，不能宣称新增AI推荐/引用或收录。

## 必须验收
- 使用合成测试数据：superseded重复引用同一Receipt不重复累计；失败Task不能核销；
  71+2技术超时不被要求登录；原始state不可被诊断改写。
- Windows全部继承门禁：前端JS、SEO自治、GEO安全领取、原版测试；
  Windows打包、签名、扫描、安装、覆盖升级、数据保留和卸载。
- 正式5平台Chrome真实网页验证Receipt必须用真实Task/外部会话证明，不能模拟；
  24h新增复测必须按实际到期后再核实。此项不能靠CI假定通过。
- 只有经过安装后的真实UI复核，才能宣称GEO业务验收完成。

## 输出
独立分支 codex/geo-818-ledger-integrity-20261018、GitHub commit、Actions结果、
Windows安装Artifact、保留#817回滚、上述已通过与未通过清单。
