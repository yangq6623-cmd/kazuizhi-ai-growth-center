"""#886 precision closure tests; synthetic data only, no external action."""
from __future__ import annotations
import os, shutil, sys, tempfile, threading, time
from pathlib import Path

ROOT=Path(__file__).resolve().parents[2]
SOURCE=ROOT/"05_V2.0.0_Source"
sys.path.insert(0,str(SOURCE))
sandbox=Path(tempfile.mkdtemp(prefix="kazuizhi-886-"))
old_local=os.environ.get("LOCALAPPDATA"); old_profile=os.environ.get("USERPROFILE")
os.environ["LOCALAPPDATA"]=str(sandbox); os.environ["USERPROFILE"]=str(sandbox)
try:
    from core import r8_23_growth_operating_system as growth
    from core import r8_22_autonomous_convergence as convergence
    from integrations.seo_public_deployer import semantic_content_fingerprint

    # Three independent cold probes must overlap, not add their latency.
    old_rows,old_gpu=growth._connector_rows,growth.gpu_status
    import integrations.ai_gateway as gateway
    old_gateway=gateway.gateway_status
    calls={"rows":0,"gpu":0,"gateway":0}
    def rows(): calls["rows"]+=1; time.sleep(.12); return {}
    def gpu(): calls["gpu"]+=1; time.sleep(.12); return {"ready":False,"rtx3060":False}
    def gate(): calls["gateway"]+=1; time.sleep(.12); return {"routes":{}}
    try:
        growth._connector_rows=rows; growth.gpu_status=gpu; gateway.gateway_status=gate
        growth._CAPABILITY_CACHE.update(at=0.0,key=None,rows=None)
        started=time.perf_counter(); growth.capability_status(force=True); elapsed=time.perf_counter()-started
        assert elapsed < .27, elapsed
        assert calls=={"rows":1,"gpu":1,"gateway":1}, calls
    finally:
        growth._connector_rows=old_rows; growth.gpu_status=old_gpu; gateway.gateway_status=old_gateway
        growth._CAPABILITY_CACHE.update(at=0.0,key=None,rows=None)

    # A new revision ID and timestamp alone must not change deployable meaning.
    one=sandbox/"one.html"; two=sandbox/"two.html"; three=sandbox/"three.html"
    one.write_text("<html><body><h1>涟水空调维修</h1><p>真实服务说明。</p><i>REVISION-AAA</i><time>2026-10-25T10:00:00+08:00</time></body></html>",encoding="utf-8")
    two.write_text("<html> <body><h1>涟水空调维修</h1><p>真实服务说明。</p><i>REVISION-BBB</i><time>2026-10-26T10:00:00+08:00</time></body></html>",encoding="utf-8")
    three.write_text("<html><body><h1>涟水空调维修</h1><p>新增真实安全说明。</p><i>REVISION-CCC</i></body></html>",encoding="utf-8")
    assert semantic_content_fingerprint(one)==semantic_content_fingerprint(two)
    assert semantic_content_fingerprint(one)!=semantic_content_fingerprint(three)

    # R8-22 stale truth remains available while one background rebuild runs.
    old_builder=convergence._build_read_only_snapshot
    calls2={"count":0}
    def build():
        calls2["count"]+=1; time.sleep(.08)
        return {"generated_at":"2026-10-27T00:00:00Z","progress":{"total":7,"completed":6}}
    try:
        convergence._build_read_only_snapshot=build
        with convergence._READ_ONLY_CACHE_LOCK:
            convergence._READ_ONLY_CACHE.update(at=0.0,value=None,refreshing=False)
        first=convergence.read_only_snapshot(force=True)
        assert first["progress"]["total"]==7
        with convergence._READ_ONLY_CACHE_LOCK: convergence._READ_ONLY_CACHE["at"]=0.0
        started=time.perf_counter(); stale=convergence.read_only_snapshot(); elapsed=time.perf_counter()-started
        assert elapsed < .04, elapsed
        assert stale["snapshot_state"]=="cached_refreshing"
        deadline=time.time()+2
        while time.time()<deadline:
            with convergence._READ_ONLY_CACHE_LOCK:
                if not convergence._READ_ONLY_CACHE["refreshing"]: break
            time.sleep(.01)
        assert calls2["count"]==2,calls2
    finally:
        convergence._build_read_only_snapshot=old_builder

    manifest=(SOURCE/"browser_extension/kazuizhi_geo/manifest.json").read_text(encoding="utf-8")
    worker=(SOURCE/"browser_extension/kazuizhi_geo/service-worker.js").read_text(encoding="utf-8")
    agent=(SOURCE/"browser_extension/kazuizhi_geo/content-agent.js").read_text(encoding="utf-8")
    operational=(SOURCE/"web/operational.js").read_text(encoding="utf-8")
    connection=(SOURCE/"web/kz_async_control_ui.js").read_text(encoding="utf-8")
    decision=(SOURCE/"web/decision_layout_patch.js").read_text(encoding="utf-8")
    assert manifest.count("https://work.n.cn/*")==2
    assert "message_channel_closed_after_possible_external_action" in worker
    assert "deadline_read_only_reconciliation" in worker
    assert "answer_still_generating" in agent
    assert "/api/r8-13/seo-geo" in operational and "/api/r8-19/geo/queue" in operational
    assert "不等于收录" in operational and "不等于社媒发布" in operational
    assert "/api/chatgpt-connector/status" in connection and "heartbeatFresh" in connection
    assert "当前活动任务 / Action" in decision
    print("PASS: #886 latency, semantic deployment guard, extension safety and UI truth")
finally:
    if old_local is None: os.environ.pop("LOCALAPPDATA",None)
    else: os.environ["LOCALAPPDATA"]=old_local
    if old_profile is None: os.environ.pop("USERPROFILE",None)
    else: os.environ["USERPROFILE"]=old_profile
    shutil.rmtree(sandbox,ignore_errors=True)
