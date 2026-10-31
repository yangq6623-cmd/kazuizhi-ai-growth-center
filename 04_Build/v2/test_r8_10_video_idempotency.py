import importlib.util
import sys
import types
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
PATCH = ROOT / "05_V2.0.0_Source" / "backend" / "r8_10_idempotency_patch.py"


def main() -> None:
    calls = {"create": 0}
    state = {
        "videos": [
            {"id": "VIDEO-ACTIVE", "campaign_id": "KZ-1", "status": "等待ChatGPT策划", "asset_ids": []},
            {"id": "VIDEO-DONE", "campaign_id": "KZ-2", "status": "已验证发布", "asset_ids": []},
        ]
    }

    promotion_pkg = types.ModuleType("promotion")
    promotion_pkg.__path__ = []
    cf = types.ModuleType("promotion.content_factory")

    def load():
        return state

    def original_create(payload):
        calls["create"] += 1
        item = {
            "id": f"VIDEO-NEW-{calls['create']}",
            "campaign_id": payload["campaign_id"],
            "status": "等待ChatGPT策划",
            "asset_ids": [],
        }
        state["videos"].append(item)
        return item

    cf._load = load
    cf.create_video = original_create
    promotion_pkg.content_factory = cf
    sys.modules["promotion"] = promotion_pkg
    sys.modules["promotion.content_factory"] = cf

    backend_pkg = types.ModuleType("backend")
    backend_pkg.__path__ = []
    server = types.ModuleType("backend.server")
    server.factory_create_video = original_create
    backend_pkg.server = server
    sys.modules["backend"] = backend_pkg
    sys.modules["backend.server"] = server

    spec = importlib.util.spec_from_file_location("backend.r8_10_idempotency_patch", PATCH)
    if spec is None or spec.loader is None:
        raise RuntimeError("cannot load idempotency patch")
    module = importlib.util.module_from_spec(spec)
    sys.modules["backend.r8_10_idempotency_patch"] = module
    spec.loader.exec_module(module)

    reused = cf.create_video({"campaign_id": "KZ-1"})
    assert reused["id"] == "VIDEO-ACTIVE"
    assert reused["idempotent_reuse"] is True
    assert calls["create"] == 0

    # Completed/non-active history must not block a genuinely new production task.
    created = cf.create_video({"campaign_id": "KZ-2"})
    assert created["id"].startswith("VIDEO-NEW-")
    assert calls["create"] == 1

    # The server route alias must point at the same hardened callable.
    reused_route = server.factory_create_video({"campaign_id": "KZ-1"})
    assert reused_route["id"] == "VIDEO-ACTIVE"
    assert reused_route["idempotent_reuse"] is True
    assert calls["create"] == 1

    print("PASS: concurrent Mission/UI video creation is idempotent without allowing duplicate active jobs.")


if __name__ == "__main__":
    main()
