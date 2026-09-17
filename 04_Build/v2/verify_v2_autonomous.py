"""Run the full V2 verifier with the R7 autonomous-nonfinancial contract.

The historical verifier still contains the pre-autonomy approval assertions. This
wrapper replaces only stale R7/autonomy assertions at verification time, while
keeping all original source, packaging, installer, data-safety and regression checks.
"""
from pathlib import Path

TARGET = Path(__file__).with_name("verify_v2.py")
text = TARGET.read_text(encoding="utf-8")
start_token = '                with urllib.request.urlopen(base + "/api/r7/agents") as response:\n'
end_token = '                check(audit["integrity"] == "verified" and len(audit["events"]) >= 8, "R7 audit trail incomplete")\n'
start = text.index(start_token)
end = text.index(end_token, start) + len(end_token)

replacement = '''                with urllib.request.urlopen(base + "/api/r7/agents") as response:
                    agents = json.load(response)
                check(len(agents["items"]) == 8 and all(x["execution"] == "auto_non_financial" for x in agents["items"]), "R7 autonomous agent roles misreported")
                check(agents.get("truth_policy") == "job_telemetry_only_no_simulated_progress", "R7 live agent truth policy missing")
                check(agents.get("summary", {}).get("total") == 8, "R7 live agent management summary missing")
                with urllib.request.urlopen(base + "/api/r7/engine") as response:
                    engine = json.load(response)
                check(engine["migration"]["result"] == "complete" and engine["audit_integrity"] == "verified", "R7 migration or audit failed")
                check(engine.get("autonomy_policy") == "auto_non_financial_finance_human_only", "R7 autonomy policy missing")
                with urllib.request.urlopen(base + "/api/r7/model-routes") as response:
                    routes = json.load(response)
                check(len(routes["routes"]) == 1 and routes["default"] == "local_rules", "Unverified external route appeared")
                automatic = post("/api/r7/jobs", {"kind": "manual_task", "title": "核查本地草稿"})
                check(automatic["state"] == "queued" and automatic["progress"] == 0, "Non-financial job was not auto-queued")
                check(automatic.get("approval_policy") == "auto_non_financial", "Automatic approval policy missing")
                finance = post("/api/r7/jobs", {"kind": "manual_task", "title": "给师傅结算并付款"})
                check(finance["state"] == "awaiting_approval" and finance.get("approval_policy") == "finance_human_only", "Finance task bypassed human approval")
                try:
                    post("/api/r7/jobs", {"kind": "auto_publish", "title": "对外发布"})
                    raise AssertionError("Unauthorized job kind accepted")
                except urllib.error.HTTPError as error:
                    check(error.code == 400, "Unauthorized job returned wrong status")
                cross_origin = urllib.request.Request(base + "/api/r7/jobs", data=b'{}', headers={"Content-Type": "application/json", "Origin": "https://untrusted.example"}, method="POST")
                try:
                    urllib.request.urlopen(cross_origin)
                    raise AssertionError("Cross-origin mutation accepted")
                except urllib.error.HTTPError as error:
                    check(error.code == 403, "Cross-origin protection returned wrong status")
                post("/api/r7/scheduler/tick", {})
                with urllib.request.urlopen(base + "/api/r7/jobs") as response:
                    jobs = json.load(response)
                automatic = next(x for x in jobs["items"] if x["id"] == automatic["id"])
                check(automatic["state"] == "completed" and automatic["progress"] == 100, "Auto-approved non-financial task did not execute")
                check(automatic.get("started_at") and automatic.get("heartbeat_at") and automatic.get("finished_at"), "Live task timestamps missing")
                local = post("/api/r7/jobs", {"kind": "diagnostics", "title": "本机体检"})
                check(local["state"] == "queued" and local.get("approval_policy") == "auto_non_financial", "Diagnostics was not auto-queued")
                post("/api/r7/scheduler/tick", {})
                with urllib.request.urlopen(base + "/api/r7/jobs") as response:
                    jobs = json.load(response)
                local = next(x for x in jobs["items"] if x["id"] == local["id"])
                check(local["state"] == "completed" and local["progress"] == 100, "Auto-approved local task did not execute")
                finance = next(x for x in jobs["items"] if x["id"] == finance["id"])
                check(finance["state"] == "awaiting_approval", "Finance task executed without human approval")
                with urllib.request.urlopen(base + "/api/r7/audit") as response:
                    audit = json.load(response)
                check(audit["integrity"] == "verified" and len(audit["events"]) >= 8, "R7 audit trail incomplete")
'''

patched = text[:start] + replacement + text[end:]
patched = patched.replace(
    'check(all(item["execution"] == "proposal_only" for item in review["tomorrow_plan"]["tasks"]), "Plan bypassed review")',
    'check(all(item["execution"] == "auto_non_financial" for item in review["tomorrow_plan"]["tasks"]), "Autonomous plan execution policy missing")',
)
patched = patched.replace(
    'check(saved_plan["tasks"][0]["execution"] == "proposal_only", "Manual plan bypassed review")',
    'check(saved_plan["tasks"][0]["execution"] == "auto_non_financial", "Manual non-financial plan was not marked for autonomous execution")',
)
namespace = {"__name__": "__main__", "__file__": str(TARGET)}
exec(compile(patched, str(TARGET), "exec"), namespace)
