"""Produce a reviewable plan; execution remains separate and allow-listed."""

from datetime import date, timedelta


ALLOWLIST = ("run_scan", "add_priority_seed", "add_owner_command")
FINANCIAL_ACTIONS = ("支付", "退款", "改价", "提现", "结算", "充值", "补贴", "赔付", "佣金打款")


def build_plan(summary, problems, opportunities):
    tasks = []
    if summary.get("status") == "not_connected":
        tasks.append({
            "title": "确认只读经营数据连接状态",
            "reason": "当前没有可验证的订单、用户或收入数据。",
            "action": "add_owner_command",
            "risk": "low",
            "execution": "proposal_only",
        })
    if opportunities:
        tasks.append({
            "title": "扫描高优先级本地需求信号",
            "reason": opportunities[0],
            "action": "run_scan",
            "risk": "low",
            "execution": "proposal_only",
        })
    return {
        "date": str(date.today() + timedelta(days=1)),
        "status": "ready_for_review",
        "tasks": tasks,
        "allowlist": list(ALLOWLIST),
        "blocked_financial_actions": list(FINANCIAL_ACTIONS),
        "execution_policy": "计划与执行分离；本页面只生成建议，不直接执行。",
        "problem_count": len(problems),
    }

