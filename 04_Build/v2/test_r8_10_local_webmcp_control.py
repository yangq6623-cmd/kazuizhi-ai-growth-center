import importlib.util
import os
import sys
import tempfile
import types
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SOURCE = ROOT / "05_V2.0.0_Source"
sys.path.insert(0, str(SOURCE))


def load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot load {path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


pkg = types.ModuleType("integrations")
pkg.__path__ = [str(SOURCE / "integrations")]
sys.modules["integrations"] = pkg
control = load_module("integrations.chatgpt_control", SOURCE / "integrations" / "chatgpt_control.py")
setattr(pkg, "chatgpt_control", control)
local = load_module("integrations.kz_local_control", SOURCE / "integrations" / "kz_local_control.py")
setattr(pkg, "kz_local_control", local)


def main() -> None:
    with tempfile.TemporaryDirectory() as temp:
        previous = os.environ.get("LOCALAPPDATA")
        os.environ["LOCALAPPDATA"] = temp
        try:
            initial = local.status()
            assert initial["available"] is True
            assert initial["server_required"] is False
            assert initial["public_port_required"] is False
            assert initial["verified"] is False

            paired = local.pair_webmcp({
                "challenge_id": "WEBMCP-CHALLENGE-001",
                "invocation_id": "WEBMCP-INVOKE-001",
                "client": "chatgpt-desktop-webmcp",
            })
            assert paired["idempotent"] is False
            state = control.control_status()
            assert state["verified"] is True
            assert state["connector_id"] == local.CONNECTOR_ID
            assert state["proof_source"] == "chatgpt_app"
            assert "refund" not in state["permissions"]
            assert local.status()["verified"] is True

            # Same invocation is idempotent; same challenge with another invocation is replay.
            replay_ok = local.pair_webmcp({
                "challenge_id": "WEBMCP-CHALLENGE-001",
                "invocation_id": "WEBMCP-INVOKE-001",
                "client": "chatgpt-desktop-webmcp",
            })
            assert replay_ok["idempotent"] is True
            try:
                local.pair_webmcp({
                    "challenge_id": "WEBMCP-CHALLENGE-001",
                    "invocation_id": "WEBMCP-INVOKE-002",
                    "client": "chatgpt-desktop-webmcp",
                })
            except ValueError as error:
                assert "重放" in str(error)
            else:
                raise AssertionError("replayed local pairing challenge was accepted")

            system = local.execute_tool("get_system_status", request_id="LOCAL-READ-001")
            assert system["tool"] == "get_system_status"
            assert system["result"]["local_control"]["verified"] is True

            mission_request = {
                "region": "涟水县",
                "service": "水电安装维修",
                "title": "涟水县水电维修真实咨询增长",
                "evidence": "老板明确要求今天重点推广涟水县水电维修并以真实咨询为目标",
                "goal": "获得可追溯的真实咨询",
                "reason": "优先围绕已明确区域与服务建立可追溯 Mission，不虚构外部结果",
                "objective": "今天重点推广涟水县水电维修，目标是获得真实咨询",
            }
            created = local.execute_tool(
                "create_mission",
                mission_request,
                request_id="LOCAL-MISSION-001",
            )
            result = created["result"]
            receipt = result["receipt"]
            mission = result["mission"]
            assert created["idempotent"] is False
            assert receipt["receipt_id"].startswith("RECEIPT-")
            assert receipt["command_id"].startswith("CMD-")
            assert receipt["mission_id"]
            assert mission["mission_id"] == receipt["mission_id"]
            assert mission["region"] == "涟水县"
            assert mission["service"] == "水电安装维修"

            duplicate = local.execute_tool(
                "create_mission",
                mission_request,
                request_id="LOCAL-MISSION-001",
            )
            assert duplicate["idempotent"] is True
            assert duplicate["result"]["receipt"]["receipt_id"] == receipt["receipt_id"]

            employees = local.execute_tool("get_ai_employee_status", request_id="LOCAL-READ-EMPLOYEES")
            assert employees["result"]["count"] == 8

            readback = local.execute_tool("get_current_mission", request_id="LOCAL-READ-MISSION")
            assert readback["result"]["active_mission"]["mission_id"] == receipt["mission_id"]

            receipts = local.execute_tool("read_receipts", {"limit": 20}, request_id="LOCAL-READ-RECEIPTS")
            ids = [item.get("receipt_id") for item in receipts["result"]["items"]]
            assert receipt["receipt_id"] in ids

            continued = local.execute_tool(
                "start_content_task",
                {"mission_id": receipt["mission_id"], "reason": "继续本机自治内容生产"},
                request_id="LOCAL-CONTENT-001",
            )
            assert continued["result"]["receipt"]["mission_id"] == receipt["mission_id"]

            try:
                local.execute_tool("refund", {}, request_id="LOCAL-FORBIDDEN-001")
            except ValueError as error:
                assert "禁止" in str(error) or "不支持" in str(error)
            else:
                raise AssertionError("financial tool was accepted")

            site_js = (SOURCE / "web" / "kz_site_tools.js").read_text(encoding="utf-8")
            assert "document.modelContext || navigator.modelContext" in site_js
            for tool_name in (
                "kazuizhi_connect_local_control",
                "kazuizhi_get_system_status",
                "kazuizhi_create_mission",
                "kazuizhi_start_content_task",
                "kazuizhi_read_receipts",
            ):
                assert tool_name in site_js
            assert "/api/kz-local-control/pair" in site_js
            assert "/api/kz-local-control/tool" in site_js
            assert "refund" not in site_js.lower()

            backend = (SOURCE / "backend" / "kz_local_control_patch.py").read_text(encoding="utf-8")
            assert "is_loopback" in backend
            assert "Cross-origin" not in backend or "localhost" in backend

            # R8-12.1 sequences optional same-PC helpers through the single
            # startup coordinator instead of racing independent memory.js loaders.
            loader = (SOURCE / "web" / "memory.js").read_text(encoding="utf-8")
            startup = (SOURCE / "web" / "r8_12_startup_coordinator.js").read_text(encoding="utf-8")
            assert "/r8_12_startup_coordinator.js" in loader
            assert "/kz_site_tools.js" in startup
            assert "/kz_local_direct_ui.js" in startup
        finally:
            if previous is None:
                os.environ.pop("LOCALAPPDATA", None)
            else:
                os.environ["LOCALAPPDATA"] = previous

    print("PASS: ChatGPT desktop WebMCP localhost -> Command -> Mission -> Receipt -> readback verified without business server, under coordinated startup.")


if __name__ == "__main__":
    main()
