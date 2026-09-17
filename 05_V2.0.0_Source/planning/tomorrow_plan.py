"""Build tomorrow's plan for autonomous non-financial execution."""

from datetime import date, timedelta
from core.storage import now_iso, write_json


ALLOWLIST = ("run_scan", "add_priority_seed", "add_owner_command", "generate_content", "local_growth")
FINANCIAL_ACTIONS = ("支付", "付款", "退款", "改价", "提现", "结算", "充值", "转账", "赔付", "补贴", "佣金打款")


def _task(title, reason, action="run_scan", risk="low"):
    return {
        "title": title,
        "reason": reason,
        "action": action,
        "risk": risk,
        "execution": "auto_non_financial",
    }


def build_plan(summary, problems, opportunities):
    tasks = []
    if summary.get("status") == "not_connected":
        tasks.append(_task(
            "复核只读经营数据连接状态",
            "当前没有可验证的订单、用户或收入数据；自动记录缺口但不编造经营数字。",
            "add_owner_command",
        ))
    if opportunities:
        tasks.append(_task(
            "扫描涟水高优先级本地需求信号",
            opportunities[0],
            "run_scan",
        ))
    tasks.append(_task(
        "根据今日结果生成下一轮本地维修增长动作",
        "持续用已验证结果和公开信号调整次日任务优先级。",
        "local_growth",
    ))
    return {
        "date": str(date.today() + timedelta(days=1)),
        "status": "auto_ready",
        "tasks": tasks,
        "allowlist": list(ALLOWLIST),
        "blocked_financial_actions": list(FINANCIAL_ACTIONS),
        "execution_policy": "非资金类运营任务默认自动执行；资金类动作始终要求人工确认。",
        "learning_policy": "只根据可追溯结果更新运营记忆、优先级和工作流参数，不静默修改程序源代码或安全边界。",
        "problem_count": len(problems),
    }


def save_manual_plan(items):
    clean = [str(item).strip() for item in items if str(item).strip()][:100]
    if not clean:
        raise ValueError("tasks must not be empty")
    plan = {
        "date": str(date.today() + timedelta(days=1)),
        "saved_at": now_iso(),
        "status": "auto_ready",
        "tasks": [_task(item, "老板手动录入，若不涉及资金则自动执行", "add_owner_command") for item in clean],
        "allowlist": list(ALLOWLIST),
        "blocked_financial_actions": list(FINANCIAL_ACTIONS),
        "execution_policy": "非资金类运营任务默认自动执行；资金类动作始终要求人工确认。",
    }
    return write_json("plans/latest_plan.json", plan)
