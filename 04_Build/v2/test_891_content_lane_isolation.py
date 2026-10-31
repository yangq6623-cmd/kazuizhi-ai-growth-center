"""Reproduce content-lane failure isolation without importing app or networking."""
import ast
from pathlib import Path
from types import SimpleNamespace


SOURCE = Path(__file__).resolve().parents[2] / "05_V2.0.0_Source" / "run.py"
module = ast.parse(SOURCE.read_text(encoding="utf-8"), filename=str(SOURCE))
function = next(
    row for row in module.body
    if isinstance(row, ast.FunctionDef) and row.name == "start_content_execution_worker"
)


class OneCycleEvent:
    def __init__(self):
        self.checks = 0

    def wait(self, _seconds):
        return False

    def is_set(self):
        self.checks += 1
        return self.checks > 1


class InlineThread:
    def __init__(self, target, **_kwargs):
        self.target = target

    def start(self):
        self.target()


names = (
    "scan_material_inbox", "ensure_pending_candidate_worker", "sync_autonomous_ops", "sync_content_plans",
    "recover_authorized_qc", "run_ai_gateway", "sync_chatgpt_handoffs",
    "bridge_sync_once", "run_publish_planning", "sync_mission_backbone",
)


def verify_cycle(failed_step):
    steps, health = [], []

    def recorder(name):
        def run(*_args, **_kwargs):
            steps.append(name)
            if name == failed_step:
                raise RuntimeError(f"isolated_{name}_failure")
        return run

    scope = {name: recorder(name) for name in names}
    scope.update({
        "threading": SimpleNamespace(Event=OneCycleEvent, Thread=InlineThread),
        "CONTENT_STARTUP_GRACE_SECONDS": 0,
        "CONTENT_WORKER_INTERVAL_SECONDS": 0,
        "runtime_set_worker_enabled": lambda *_args: None,
        "_runtime_mark": lambda _name, **kwargs: health.append(kwargs),
    })
    exec(compile(ast.Module(body=[function], type_ignores=[]), str(SOURCE), "exec"), scope)
    scope["start_content_execution_worker"]()
    assert steps.count(failed_step) == 1, "A failed external operation was retried in the same cycle"
    assert "run_publish_planning" in steps, "Publishing lane was skipped"
    assert "sync_mission_backbone" in steps, "Mission ledger reconciliation was skipped"
    assert "run_ai_gateway" in steps, "Router lane was skipped"
    assert any(not row.get("ok", True) for row in health), "The failed step was not reported"


for failed in (
    "scan_material_inbox", "ensure_pending_candidate_worker",
    "run_ai_gateway", "run_publish_planning",
):
    verify_cycle(failed)
print("PASS: material, ComfyUI, Router and publish failure each spare sibling lanes")
