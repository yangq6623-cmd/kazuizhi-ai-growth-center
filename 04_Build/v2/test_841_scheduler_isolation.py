"""#841 scheduler failure containment -- static AST isolation, zero side effects."""
from __future__ import annotations

import ast
from pathlib import Path
from types import SimpleNamespace

SRC = Path(__file__).resolve().parents[2] / "05_V2.0.0_Source" / "backend" / "r8_20_seo_geo_growth_patch.py"


def main():
    source = ast.parse(SRC.read_text(encoding="utf-8"), filename=str(SRC))
    target = next(node for node in source.body if isinstance(node, ast.FunctionDef) and node.name == "_combined_run")
    isolated = ast.Module(body=[target], type_ignores=[])
    calls = []

    def fail(label):
        def _call(*args, **kwargs):
            calls.append(label)
            raise RuntimeError(label + "_disconnected")
        return _call

    def succeed(label):
        def _call(*args, **kwargs):
            calls.append(label)
            return {"ok": True, "worker": label}
        return _call

    def cycle(*, upstream, intelligence, geo, connector):
        calls.clear()
        ns = {
            "_ORIGINAL_RUN": fail("seo") if upstream else succeed("seo"),
            "growth": SimpleNamespace(run_once=fail("growth") if intelligence else succeed("growth")),
            "geo_growth": SimpleNamespace(run_once=fail("geo") if geo else succeed("geo")),
            "connector_router": SimpleNamespace(sync_growth_health=fail("connector") if connector else succeed("connector")),
            "runtime_resilience": SimpleNamespace(snapshot=succeed("runtime")),
        }
        exec(compile(isolated, str(SRC), "exec"), ns)
        result = ns["_combined_run"]()
        assert calls == ["connector", "seo", "growth", "geo", "runtime"], calls
        assert result["geo_growth_os"]["ok"] is (not geo), result
        assert result["r8_20_growth"]["ok"] is (not intelligence), result
        assert result["connector_routes"]["ok"] is (not connector), result
        if upstream:
            assert result["ok"] is False and result["reason"] == "seo_geo_step_failed"
        return result

    cycle(upstream=False, intelligence=False, geo=False, connector=False)
    cycle(upstream=True, intelligence=False, geo=False, connector=False)
    cycle(upstream=False, intelligence=True, geo=False, connector=False)
    cycle(upstream=False, intelligence=False, geo=False, connector=True)
    cycle(upstream=True, intelligence=True, geo=False, connector=True)
    cycle(upstream=False, intelligence=False, geo=True, connector=False)
    print("#841 scheduler sibling-worker isolation: PASS")


if __name__ == "__main__":
    main()
