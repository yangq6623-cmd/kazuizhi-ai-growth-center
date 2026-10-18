import importlib
import json
import os
import sys
import tempfile
import threading
from pathlib import Path
from urllib.error import HTTPError
from urllib.request import Request, urlopen


SOURCE = Path(__file__).resolve().parents[2] / "05_V2.0.0_Source"
sys.path.insert(0, str(SOURCE))


def expect_error(callable_, text):
    try:
        callable_()
    except ValueError as error:
        assert text in str(error), (text, str(error))
    else:
        raise AssertionError(f"Expected ValueError containing: {text}")


with tempfile.TemporaryDirectory() as temp_dir:
    os.environ["LOCALAPPDATA"] = temp_dir

    import core.account_registry as registry
    import integrations.desktop_browser_session as browser_session
    import core.r8_growth_ops as growth

    importlib.reload(registry)
    importlib.reload(browser_session)
    importlib.reload(growth)

    account = registry.register_official_identity("douyin", "lshome-main", "ci-main", method="desktop_browser_qr")
    registry.set_auth_state(account["account_id"], "connected", method="desktop_browser_qr")
    registry.update_scope(account["account_id"], services=["家电维修"], regions=["涟水县"])
    second_account = registry.register_official_identity("douyin", "lshome-service", "ci-service", method="desktop_browser_qr")
    registry.set_auth_state(second_account["account_id"], "connected", method="desktop_browser_qr")
    registry.update_scope(second_account["account_id"], services=["家电维修"], regions=["涟水县"])
    sessions = browser_session._state()
    for item in (account, second_account):
        sessions["sessions"].append({"account_id": item["account_id"], "platform": "douyin", "status": "owner_confirmed"})
    browser_session._save(sessions)

    signal_payload = {
        "platform": "douyin",
        "source_id": "public-post-001",
        "source_url": "https://example.invalid/public-post-001",
        "summary": "涟水用户咨询冰箱不制冷，询问是否可以上门检查",
        "region": "涟水县",
        "service_category": "家电维修",
        "intent_level": "high",
        "recommended_action": "reply",
    }
    first_signal = growth.ingest_signal(signal_payload)
    duplicate = growth.ingest_signal(signal_payload)
    assert first_signal["created"] is True
    assert duplicate["duplicate"] is True
    signal_id = first_signal["item"]["signal_id"]
    routed = growth.route_signal({"signal_id": signal_id})
    assert routed["signal"]["route_state"] == "ready"
    assert routed["account"]["account_id"] in {account["account_id"], second_account["account_id"]}
    account = routed["account"]

    case = growth.create_growth_case({"signal_id": signal_id})["item"]
    content = growth.create_content_brief({"growth_id": case["growth_id"]})["item"]
    assert len(content["committee"]) == 8
    growth.review_content({"content_id": content["content_id"], "action": "approve", "reviewer": "owner"})

    video = growth.create_video_job({"content_id": content["content_id"]})["item"]
    assert video["status"] in {"waiting_worker", "queued"}
    expect_error(
        lambda: growth.schedule_publish({
            "content_id": content["content_id"],
            "account_id": account["account_id"],
            "owner_approved": False,
        }),
        "老板",
    )

    publish = growth.schedule_publish({
        "content_id": content["content_id"],
        "account_id": account["account_id"],
        "owner_approved": True,
        "reviewer": "owner",
    })
    expect_error(
        lambda: growth.record_publish_receipt({
            "publish_id": publish["publish_id"],
            "result": "success",
            "executed_by": "desktop_browser",
        }),
        "平台内容 ID",
    )
    receipt = growth.record_publish_receipt({
        "publish_id": publish["publish_id"],
        "result": "success",
        "executed_by": "desktop_browser",
        "platform_content_id": "DY-REAL-001",
        "url": "https://example.invalid/video/DY-REAL-001",
    })
    assert receipt["status"] == "published"

    message_result = growth.ingest_message({
        "platform": "douyin",
        "account_id": account["account_id"],
        "user_ref": "public-user-001",
        "content": "想预约明天下午检查冰箱",
        "kind": "dm",
        "source": "human_import",
    })
    conversation_id = message_result["conversation"]["conversation_id"]
    lead = growth.upsert_lead({
        "conversation_id": conversation_id,
        "region": "涟水",
        "service_category": "家电维修",
        "stage": "qualified",
    })
    attribution = growth.record_attribution({
        "lead_id": lead["lead_id"],
        "order_id": "ORDER-VERIFIED-001",
        "source": "manual_confirmation",
        "order_status": "completed",
    })
    assert attribution["created"] is True
    growth.update_conversation({"conversation_id": conversation_id, "state": "closed", "do_not_contact": True})
    expect_error(
        lambda: growth.ingest_message({
            "platform": "douyin",
            "account_id": second_account["account_id"],
            "user_ref": "public-user-001",
            "direction": "outbound",
            "content": "换一个矩阵号继续联系",
            "kind": "dm",
        }),
        "禁止跨账号",
    )

    metrics = growth.record_metrics({
        "publish_id": publish["publish_id"],
        "checkpoint": "72h",
        "source": "manual_verified",
        "impressions": 120,
        "plays": 90,
        "completions": 50,
        "likes": 8,
        "comments": 3,
        "saves": 2,
        "shares": 1,
        "dms": 1,
        "consultations": 1,
        "orders": 1,
        "completed_orders": 1,
    })
    assert metrics["metrics"]["completed_orders"] == 1
    cycle = growth.run_learning_cycle({"next_change": "保留真实问题开场，下一轮测试更清楚的服务范围"})
    assert cycle["cycle"]["growth_id"] == case["growth_id"]

    sensitive = dict(signal_payload, source_id="public-post-002", password="forbidden")
    expect_error(lambda: growth.ingest_signal(sensitive), "不接收密码")
    human_message = growth.ingest_message({
        "platform": "douyin",
        "account_id": account["account_id"],
        "user_ref": "public-user-002",
        "content": "我要投诉并申请退款",
        "kind": "dm",
    })
    assert human_message["conversation"]["state"] == "human_required"

    status = growth.dashboard()
    assert status["delivery"]["phase"] == "R8-08"
    assert status["counts"]["signals"] == 1
    assert status["counts"]["growth_cases"] == 1
    assert status["counts"]["content_jobs"] == 1
    assert status["counts"]["publish_jobs"] == 1
    assert status["counts"]["leads"] == 1
    assert len(status["gates"]) == 9
    diagnostics = growth.diagnostics()
    assert diagnostics["summary"]["schema"] == "kazuizhi-r8-growth-ops/v1"
    assert diagnostics["checks"]

    from backend.server import create_server

    server = create_server(0)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    base = f"http://127.0.0.1:{server.server_port}"
    try:
        with urlopen(base + "/api/status", timeout=5) as response:
            http_status = json.loads(response.read().decode("utf-8"))
        assert http_status["r8_phase"] == "R8-09"
        assert http_status["runtime_build"] == "KZ-ENTERPRISE-V2.2.2-R8-AUTONOMOUS-20260922"
        assert "r8_complete_growth_operations_center" in http_status["capabilities"]
        with urlopen(base + "/api/r8/growth/summary", timeout=5) as response:
            http_summary = json.loads(response.read().decode("utf-8"))
        assert http_summary["schema"] == "kazuizhi-r8-growth-ops/v1"
        bad_request = Request(
            base + "/api/r8/growth/signals",
            data=b"{}",
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        try:
            urlopen(bad_request, timeout=5)
        except HTTPError as error:
            assert error.code == 400
        else:
            raise AssertionError("Invalid R8 signal request should be rejected")
    finally:
        server.shutdown()
        server.server_close()

print("PASS: R8-00 through R8-08 truthful growth loop runs under the R8-09 autonomous Mission core")
