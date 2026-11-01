"""One-cycle scheduler isolation using only mocks; never import production workers."""
import ast
from pathlib import Path
from types import SimpleNamespace


SOURCE = Path(__file__).resolve().parents[2] / "05_V2.0.0_Source" / "run.py"
module = ast.parse(SOURCE.read_text(encoding="utf-8"), filename=str(SOURCE))
function = next(row for row in module.body if isinstance(row, ast.FunctionDef) and row.name == "start_scheduler")


class Event:
    def __init__(self):
        self.checks = 0

    def wait(self, _seconds):
        return False

    def is_set(self):
        self.checks += 1
        return self.checks > 1


class Thread:
    def __init__(self, target, **_kwargs):
        self.target = target

    def start(self):
        self.target()


NAMES = (
    "reconcile_command_execution", "ensure_daily_workforce", "ensure_daily_review",
    "run_due_jobs", "refresh_decision_center", "export_decision_handoff",
    "_sync_r8_17_remote_agent", "run_seo_geo_autonomy", "seo_geo_autonomy_status",
    "seo_technical_audit_due", "seo_geo_dashboard", "run_seo_technical_audit",
)


def cycle(failed):
    calls, health = [], []

    def action(name):
        def run(*_args, **_kwargs):
            calls.append(name)
            if name == failed:
                raise RuntimeError("isolated_" + name)
            if name == "seo_geo_autonomy_status":
                return {"enabled": True, "mode": "autonomous", "policy": {"auto_technical_audit": True}}
            if name == "seo_geo_dashboard":
                return {"summary": {"public_pages": 1}}
            return True
        return run

    clock = iter((0, 100, 100))
    scope = {name: action(name) for name in NAMES}
    scope.update({
        "threading": SimpleNamespace(Event=Event, Thread=Thread),
        "time": SimpleNamespace(monotonic=lambda: next(clock)),
        "SCHEDULER_STARTUP_GRACE_SECONDS": 0,
        "HEAVY_CONTROL_STARTUP_GRACE_SECONDS": 0,
        "HEAVY_CONTROL_INTERVAL_SECONDS": 300,
        "SCHEDULER_INTERVAL_SECONDS": 0,
        "runtime_set_worker_enabled": lambda *_args: None,
        "_runtime_mark": lambda _name, **kwargs: health.append(kwargs),
    })
    exec(compile(ast.Module(body=[function], type_ignores=[]), str(SOURCE), "exec"), scope)
    scope["start_scheduler"]()
    assert calls.count(failed) == 1, "A failed step was retried in one cycle"
    for independent in ("ensure_daily_workforce", "run_due_jobs", "run_seo_geo_autonomy", "run_seo_technical_audit"):
        assert independent in calls, f"{independent} was skipped after {failed}"
    assert health and health[-1]["ok"] is False, "The failed step was not reported"
    assert failed in str(health[-1].get("error")), "Failed step identity was lost"


for name in ("reconcile_command_execution", "refresh_decision_center", "_sync_r8_17_remote_agent"):
    cycle(name)
print("PASS: command, manager and remote-agent failures spare independent scheduler work")
