# R8-10 异步 AI 控制总线

## 目标

日常运营不再依赖 Work/Codex 或持续 Site Tools 会话。

主链：

`普通 ChatGPT → PRIVATE GitHub Control Bus → 本机 KZ Agent → Mission/R7/R8 → Receipt → 普通 ChatGPT`

辅助链：

- Site Tools/WebMCP：同机实时控制，可用时增强，不在线也不阻断已批准 Mission。
- Work/Codex：仅用于软件检查、修复、代码与架构升级。
- Relay：远程备用。

## 强制安全规则

1. 控制总线必须使用**独立 PRIVATE GitHub 仓库**。
2. 当前 `kazuizhi-ai-growth-center` 源码仓库是公共仓库，代码会主动拒绝把它当控制总线。
3. 本机只需要最小权限 GitHub Token，建议仅授予控制总线仓库 Contents Read/Write。
4. Token 不写入源码、不写入 Decision Pack、不返回前端；当前从环境变量 `KZ_CONTROL_BUS_TOKEN` 读取。
5. 总线不开放资金、退款、提现、最终发布审批、账号验证、验证码、人脸或重要数据删除。
6. 总线同步成功不等于“实时 ChatGPT 已连接”。实时连接仍必须由真实 Site Tools/Connector Command→Receipt 证明。
7. 没有真实平台 URL/Post ID/回执，不得写成已发布；没有真实咨询/订单来源，不得写成经营成功。

## 本机环境变量

```text
KZ_CONTROL_BUS_REPO=<owner>/<private-repo>
KZ_CONTROL_BUS_BRANCH=main
KZ_CONTROL_BUS_TOKEN=<fine-grained-token>
KZ_CONTROL_BUS_POLL_SECONDS=60
KZ_CONTROL_BUS_ENABLED=true
```

没有配置控制总线时，本地已批准 Mission 仍可继续自治；状态页显示“待配置独立私有仓库”，而不是把整个系统判定为故障。

## 仓库目录

```text
/commands
    CMD-20260923-001.json
/receipts
    CMD-20260923-001.json
/state
    system_health.json
```

## Decision Pack v1

```json
{
  "schema": "kz.decision-pack.v1",
  "command_id": "CMD-20260923-001",
  "decision_pack_id": "DP-20260923-001",
  "issued_at": "2026-09-23T12:00:00+08:00",
  "valid_until": "2026-09-26T12:00:00+08:00",
  "source": "chatgpt_personal_chat",
  "decision": {
    "action": "create_mission",
    "region": "涟水县",
    "service": "水电安装维修",
    "title": "涟水县水电维修真实咨询增长",
    "evidence": "老板明确要求重点推广该区域与服务",
    "goal": "获得可追溯的真实咨询",
    "reason": "ChatGPT 一次性形成高层经营决策，本机负责持续执行"
  },
  "autonomy": {
    "allowed": [
      "content_production",
      "asset_routing",
      "technical_qc",
      "seo_content",
      "business_monitoring"
    ],
    "human_gates": [
      "final_video_review",
      "manual_verification",
      "money"
    ]
  }
}
```

同一个 `command_id` 再次出现时必须具有完全相同的 payload hash；否则本机拒绝为重放/篡改。Decision Pack 到期后不会继续执行。

## Receipt

本机接受 Decision Pack 后写回：

```text
RECEIPT-BUS-...
command_id
Decision Pack ID
Mission ID
执行状态
payload hash
真实本地结果
```

Receipt 只证明本地决策进入 Mission 链，不证明平台发布、SEO收录、咨询或订单成功。
