import importlib.util
import sys
import types
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SOURCE = ROOT / "05_V2.0.0_Source"


def load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot load {path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def main():
    backend_pkg = types.ModuleType("backend")
    backend_pkg.__path__ = [str(SOURCE / "backend")]
    sys.modules["backend"] = backend_pkg

    deep = types.ModuleType("backend.deep_productization_patch")
    deep._active_id = lambda data: data.get("active_campaign_id") or ""
    deep._current_mission_videos = lambda data: []
    sys.modules["backend.deep_productization_patch"] = deep
    setattr(backend_pkg, "deep_productization_patch", deep)

    patch = load_module(
        "backend.r8_10_state_convergence_patch",
        SOURCE / "backend" / "r8_10_state_convergence_patch.py",
    )

    data = {
        "active_campaign_id": "KZ-ACTIVE",
        "videos": [
            {
                "id": "VIDEO-CURRENT",
                "campaign_id": "KZ-ACTIVE",
                "status": "等待ChatGPT质检",
                "retry_count": 0,
            },
            {
                "id": "VIDEO-OLD-FAILED",
                "campaign_id": "KZ-ACTIVE",
                "status": "异常待处理",
                "retry_count": 3,
                "plan_received_at": "2099-01-01T00:00:00+08:00",
            },
            {
                "id": "VIDEO-OTHER",
                "campaign_id": "KZ-OTHER",
                "status": "异常待处理",
                "retry_count": 3,
            },
        ],
    }
    current = patch._current_mission_videos(data)
    assert [x["id"] for x in current] == ["VIDEO-CURRENT"]
    assert deep._current_mission_videos is patch._current_mission_videos

    # A real current failure must remain visible rather than being hidden.
    data["videos"] = [
        {"id": "VIDEO-CURRENT-FAILED", "campaign_id": "KZ-ACTIVE", "status": "异常待处理", "retry_count": 3},
        {"id": "VIDEO-OLD-OK", "campaign_id": "KZ-ACTIVE", "status": "等待生产", "retry_count": 0},
    ]
    current = patch._current_mission_videos(data)
    assert current[0]["id"] == "VIDEO-CURRENT-FAILED"
    assert current[0]["status"] == "异常待处理"

    print("PASS: owner attention follows the newest active-Mission video; stale historical failures remain audit-only.")


if __name__ == "__main__":
    main()
