"""Field gate: GEO owner state must remain readable while writes hold the JSON lock."""
from __future__ import annotations

import os
import sys
import tempfile
import threading
from pathlib import Path

SRC = Path(__file__).resolve().parents[2] / "05_V2.0.0_Source"
sys.path.insert(0, str(SRC))

from core import storage
from core import geo_growth_orchestrator as geo
from core import geo_growth_publish_bridge as publish_bridge
from core import geo_validation
from core import geo_autonomy
from integrations import ai_gateway, seo_public_deployer


def run() -> None:
    previous = os.environ.get("LOCALAPPDATA")
    previous_key = os.environ.get("OPENAI_API_KEY")
    try:
        with tempfile.TemporaryDirectory() as directory:
            os.environ["LOCALAPPDATA"] = directory
            os.environ["OPENAI_API_KEY"] = "synthetic-verified-key"
            growth = dict(geo.DEFAULT)
            growth.update({
                "opportunities": [{"id": "op1", "state": "waiting_publish",
                                   "created_at": storage.now_iso(), "asset_stage": "QC_PASSED"}],
                "enabled": True, "paused": False, "last_run_at": storage.now_iso(),
            })
            storage.write_json(geo.STORE, growth)
            storage.write_json(geo_validation.RECEIPTS_PATH, {
                "receipts": [
                    {"question_id": "D01", "official_truth": True,
                     "evidence_level": "A", "test_method": "browser"},
                    {"question_id": "D02", "official_truth": True,
                     "evidence_level": "B", "test_method": "manual"},
                    {"question_id": "D03", "provider": "cloud_auto",
                     "official_truth": False, "evidence_level": "C"},
                ],
            })
            storage.write_json(geo_autonomy.STORE, {
                "enabled": True, "target": 1, "cycle_started_at": "",
            })
            storage.write_json(ai_gateway.CONFIG_PATH, {
                "profiles": {"cloud": {"label": "豆包API", "endpoint": "https://example.com/v1",
                                       "model": "test-model"}},
            })
            storage.write_json(ai_gateway.STATE_PATH, {
                "routes": {"cloud": {"last_test_at": storage.now_iso(), "last_error": ""}},
            })
            storage.write_json(seo_public_deployer.STORE, {"enabled": False})
            report = {}
            finished = threading.Event()

            def read_owner():
                try:
                    report["growth"] = geo.fast_status()
                    report["published"] = publish_bridge.fast_status()
                except Exception as error:
                    report["error"] = repr(error)
                finally:
                    finished.set()

            # This simulates an occupied Windows write lock; the new snapshot
            # reader must finish *before* the lock is released.
            with storage._JSON_IO_LOCK:
                worker = threading.Thread(target=read_owner, daemon=True)
                worker.start()
                assert finished.wait(1.5), "GEO owner reader still waits for global JSON writer lock"
                if report.get("error"):
                    raise AssertionError(report["error"])
                direct = report["growth"]
                assert direct["status_mode"] == "fast_snapshot", direct
                assert direct["formal_ab_completed"] == 2, direct
                assert direct["summary"]["signals"] == 1, direct
                assert direct["summary"]["waiting_publish"] == 1, direct
                assert direct["cloud"]["ready"] is True, direct
                assert report["published"]["publish_connector"]["ready"] is False
            assert geo_validation.dashboard()["official"]["tested"] == 2
            print("PASS: GEO fast/read-only status bypasses global JSON lock")
            print("PASS: 2 formal A/B receipts, 1 C signal, publish readiness truthful")
    finally:
        if previous is None:
            os.environ.pop("LOCALAPPDATA", None)
        else:
            os.environ["LOCALAPPDATA"] = previous
        if previous_key is None:
            os.environ.pop("OPENAI_API_KEY", None)
        else:
            os.environ["OPENAI_API_KEY"] = previous_key


if __name__ == "__main__":
    run()
