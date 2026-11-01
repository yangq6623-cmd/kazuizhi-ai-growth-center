"""SEO connector status isolation: AST/mocks only, no publication or network."""
import ast
from pathlib import Path
from types import SimpleNamespace


SOURCE = Path(__file__).resolve().parents[2] / "05_V2.0.0_Source" / "core" / "seo_geo_autonomy.py"
module = ast.parse(SOURCE.read_text(encoding="utf-8"), filename=str(SOURCE))
function = next(node for node in module.body if isinstance(node, ast.FunctionDef) and node.name == "_external_readiness")


def verify(failed):
    calls = []

    def status(name):
        def run():
            calls.append(name)
            if name == failed:
                raise OSError(f"{name} temporarily offline")
            if name == "publish":
                return {"ready": True}
            return {"connectors": {"safe": {"configured": True, "ready": True}}}
        return run

    scope = {
        "seo_public_deployer": SimpleNamespace(status=status("publish")),
        "search_engine_submitter": SimpleNamespace(status=status("search")),
    }
    exec(compile(ast.Module(body=[function], type_ignores=[]), str(SOURCE), "exec"), scope)
    result = scope["_external_readiness"]({"technical": {"public_site": {"reachable": True}}})
    assert calls == ["publish", "search"], "One failed connector suppressed its independent sibling"
    if failed == "publish":
        assert not result["publish_connector_ready"]
        assert result["ready_search_connectors"] == ["safe"]
        assert result["publish_connector_reason"] == "publish_connector_status_error"
    else:
        assert result["publish_connector_ready"]
        assert not result["ready_search_connectors"]
        assert result["search_submitter"]["reason"] == "search_submitter_status_error"


verify("publish")
verify("search")
print("PASS: publish and search status failures do not suppress sibling readiness")
