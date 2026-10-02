"""Offline release gate for R8-23 Final Autonomous Growth OS."""
from __future__ import annotations

import os
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "05_V2.0.0_Source"
CORE = SRC / "core" / "r8_23_growth_operating_system.py"
PATCH = SRC / "backend" / "r8_23_growth_os_patch.py"
UI = SRC / "web" / "r8_23_growth_os.js"
BUILD = SRC / "web" / "build_info.js"
TRUTH_PATCH = SRC / "core" / "r8_20_growth_truth_patch.py"
SCOPE = ROOT / "04_Build" / "v2" / "R8_23_FINAL_AUTONOMOUS_GROWTH_OS_SCOPE.md"


def main():
    old_local = os.environ.get("LOCALAPPDATA")
    with tempfile.TemporaryDirectory() as tmp:
        os.environ["LOCALAPPDATA"] = tmp
        sys.path.insert(0, str(SRC))
        try:
            from core import r8_23_growth_operating_system as growth

            # Organization: exactly eight persistent employee roles, not generic lanes.
            assert len(growth.AI_EMPLOYEES) == 8
            names = {x["name"] for x in growth.AI_EMPLOYEES}
            assert names == {"市场情报员", "SEO/GEO 增长员", "内容运营员", "社媒运营员", "短视频运营员", "本地增长员", "用户转化员", "数据复盘员"}

            engines = {x["id"] for x in growth.BUSINESS_ENGINES}
            assert engines == {"repair_services", "personal_tasks"}
            for engine in growth.BUSINESS_ENGINES:
                assert engine["outcomes"][-1] == "order"
                assert not ({"money", "amount", "revenue", "profit", "roi"} & set(engine["outcomes"]))

            required_caps = {
                "chatgpt_controller", "local_model", "rtx3060", "doubao_cloud",
                "seo_website", "search_submission", "formal_geo_browser", "remote_agent",
                "social_distribution", "mini_program", "business_data",
            }
            assert required_caps <= set(growth.CAPABILITIES)
            assert growth.CAPABILITIES["local_model"]["truth_level"] == "C_auxiliary"
            assert growth.CAPABILITIES["doubao_cloud"]["truth_level"] == "C_auxiliary"
            assert growth.CAPABILITIES["formal_geo_browser"]["truth_level"] == "formal_A_B_evidence"
            assert growth.CAPABILITIES["social_distribution"]["autonomy"] == "graded_L1_L4"

            mission = {
                "mission_id": "MISSION-R823", "command_id": "CMD-R823", "command_objective":
                "7x24推广卡嘴子本地维修综合服务平台，同时持续建设个人任务增长；SEO/GEO、内容、视频、转化都按真实结果优化。",
            }
            plan = {"plan_id": "PLAN-R823", "objective": mission["command_objective"]}
            packages = growth.work_packages(mission, plan)
            assert len(packages) == 8
            assert all(x.get("employee_owner") for x in packages)
            assert all(x.get("capability_candidates") for x in packages)
            assert all("Receipt/Evidence" in x.get("expected_return", "") for x in packages)
            assert all(set(x.get("business_engines") or []) == engines for x in packages)

            # Utilization is evidence of invocation, separate from connector readiness.
            first = growth.record_utilization("local_model", success=True, result={"processed": 2}, reason="ci")
            second = growth.record_utilization("local_model", success=False, reason="ci_failure")
            assert first["invoke_count"] == 1
            assert second["invoke_count"] == 2
            assert second["success_count"] == 1 and second["failure_count"] == 1

            snap = growth.snapshot(mission, plan)
            assert snap["controller"]["exclusive_strategy_authority"] is True
            assert snap["outcome_scope"][-1] == "order"
            assert set(snap["forbidden_outcome_scope"]) == {"money", "amount", "revenue", "profit", "roi"}
            assert "连接存在不等于自动发布权限" in snap["external_authorization"]
            assert "不为展示而强制调用" in snap["operating_rule"]
            assert "正式外部Evidence" in snap["truth_rule"]

            core = CORE.read_text(encoding="utf-8")
            patch = PATCH.read_text(encoding="utf-8")
            ui = UI.read_text(encoding="utf-8")
            build = BUILD.read_text(encoding="utf-8")
            truth_patch = TRUTH_PATCH.read_text(encoding="utf-8")
            scope = SCOPE.read_text(encoding="utf-8")
            for marker in ("AI_EMPLOYEES", "BUSINESS_ENGINES", "CAPABILITIES", "record_utilization", "work_packages", "annotate_current_jobs", "gpu_status"):
                assert marker in core, marker
            for marker in ("/api/r8-23/growth-os", "/api/r8-23/growth-os/utilization", "convergence.controller_tick", "r8_23_growth_operating_system", "r8_23_growth_os.js"):
                assert marker in patch, marker
            # Windows owner UI must never flash a console window for the frequent
            # NVIDIA capability probe.  The probe is hidden and cached, while the
            # original truth semantics remain unchanged.
            for marker in ("GPU_STATUS_TTL_SECONDS", "CREATE_NO_WINDOW", "STARTF_USESHOWWINDOW", "SW_HIDE", "growth_os.gpu_status = _silent_gpu_status"):
                assert marker in patch, marker
            for marker in ("R8-23 · FINAL 7×24 AUTONOMOUS GROWTH OS", "ChatGPT 总脑", "双增长引擎", "8个AI员工", "能力利用情况"):
                assert marker in ui, marker
            # R8-23.1 collapses duplicated technical/legacy surfaces and reads
            # SEO/GEO truth into the same owner cockpit instead of stacking more
            # full-size dashboards.
            for marker in ("R8-23.1 · 老板运营总览", "/api/r8-22/autonomy", "/api/r8-20/seo-geo?days=30", "kz-r8-23-legacy", "高级分析、内容治理与运行保障", "只显示真实分配/调用"):
                assert marker in ui, marker
            assert "r8_23_growth_os_patch" in truth_patch
            assert 'phase: "R8-23"' in build
            assert "Autonomous Growth OS" in build
            for marker in ("ChatGPT is the only strategic controller", "Two business growth engines", "Eight AI employees", "Funds remain permanently human-only"):
                assert marker in scope, marker

            print("PASS: R8-23 keeps ChatGPT as sole controller, preserves truth gates, suppresses GPU console flashing, and converges owner UI into a compact truthful cockpit")
        finally:
            if sys.path and sys.path[0] == str(SRC):
                sys.path.pop(0)
            if old_local is None:
                os.environ.pop("LOCALAPPDATA", None)
            else:
                os.environ["LOCALAPPDATA"] = old_local


if __name__ == "__main__":
    main()
