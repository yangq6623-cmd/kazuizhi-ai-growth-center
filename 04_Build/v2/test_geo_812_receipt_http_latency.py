"""#812 local HTTP Receipt regression: slow analysis must not time out Chrome.

Only loopback HTTP + synthetic LOCALAPPDATA. No external AI submission.
"""
import atexit
import json
import os
from pathlib import Path
import shutil
import sys
import tempfile
import threading
import time
from http.server import ThreadingHTTPServer
from urllib.request import Request, urlopen
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "05_V2.0.0_Source"))
TEST_ROOT = Path(tempfile.mkdtemp(prefix=".kz-geo-812-http-", dir=ROOT))
atexit.register(shutil.rmtree, TEST_ROOT, True)
os.environ["LOCALAPPDATA"] = str(TEST_ROOT)

from core import geo_validation as geo
from integrations import geo_browser_agent as agent
from backend import r8_19_geo_validation_patch as bridge


def main():
    geo.bootstrap_question_set(force=True)
    q = geo.question_set()["questions"][0]
    registration = agent.register({
        "owner_confirmed": True, "agent_id": "kz-r8-28-http-812",
        "browser": "chrome", "sessions": [{"platform": "doubao_web", "state": "ready"}]
    })
    token = registration["agent_token"]
    geo._save_queue({"tasks": [{
        "task_id": "HTTP-812-TASK", "question_id": q["question_id"],
        "question_text": q["question_text"], "question_type": q["question_type"],
        "question_set_version": q["question_set_version"],
        "provider": "doubao_web", "expected_platform": "doubao_web",
        "test_method": "browser", "state": "running",
        "run_id": "HTTP-812-RUN", "executor_id": "kz-r8-28-http-812",
        "retry_count": 0,
    }]})
    geo._save_receipts({"receipts": []})
    server = ThreadingHTTPServer(("127.0.0.1", 0), bridge.server.DashboardHandler)
    server.daemon_threads = True
    served = threading.Thread(target=server.serve_forever, daemon=True)
    served.start()
    route = f"http://127.0.0.1:{server.server_address[1]}/api/r8-27/geo-browser-agent/receipt"
    body = json.dumps({
        "agent_token": token, "task_id": "HTTP-812-TASK",
        "platform": "doubao_web",
        "session_url": "https://www.doubao.com/chat/synthetic-812",
        "raw_answer": "合成完整回答，仅在隔离本地接口测试。"
    }).encode("utf-8")
    def post():
        request = Request(route, body, headers={"Content-Type": "application/json"}, method="POST")
        with urlopen(request, timeout=2.5) as response:
            assert response.status == 200
            return json.load(response)["result"]

    try:
        with patch.object(bridge, "_refresh_analysis", side_effect=lambda: time.sleep(4)):
            started = time.monotonic()
            first = post()
            elapsed = time.monotonic() - started
            assert elapsed < 2.5, f"receipt ACK waited for slow analysis: {elapsed}"
            duplicate = post()
            assert duplicate["already_recorded"] is True
            assert first["evidence_id"] == duplicate["evidence_id"]
            assert len(geo._load_receipts()["receipts"]) == 1
            assert geo._find_task("HTTP-812-TASK")[1]["state"] == "succeeded"
    finally:
        server.shutdown()
        server.server_close()
    print("PASS #812: actual loopback HTTP Receipt returns before 4-second analysis; duplicate ACK is idempotent")


if __name__ == "__main__":
    main()
