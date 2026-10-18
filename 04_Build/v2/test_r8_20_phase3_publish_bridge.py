from __future__ import annotations

import json
import os
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SOURCE = ROOT / "05_V2.0.0_Source"
if str(SOURCE) not in sys.path:
    sys.path.insert(0, str(SOURCE))


def require(condition, message):
    if not condition:
        raise AssertionError(message)


def main():
    with tempfile.TemporaryDirectory(prefix="kz-r820-phase3-bridge-") as temp:
        previous = os.environ.get("LOCALAPPDATA")
        os.environ["LOCALAPPDATA"] = temp
        try:
            from core import geo_phase3_seo_bridge as bridge
            from core import seo_geo_growth

            seo_geo_growth.ensure_baseline()
            opportunity = bridge.upsert_opportunity({
                "region": "涟水县",
                "service": "水电安装维修",
                "keyword": "涟水县水电安装维修官方服务信息-Phase3回归",
                "intent": "GEO缺口修复",
                "priority": "S",
                "source": "GEO Phase 3 · official_citation_missing",
                "source_ref": "GEO-RECEIPT-TEST-P3",
            })
            plan = {
                "plan_id": "GEO3-TEST",
                "status": "waiting_publish",
                "actions": [{
                    "action_id": "GEO3-A01-test",
                    "job_state": "completed",
                    "opportunity_id": opportunity["id"],
                }],
            }
            prepared = bridge.prepare_phase3_assets(plan)
            require(prepared["targeted"] == 1, "completed Phase3 action must target exactly its SEO opportunity")
            require(len(prepared["created"]) == 1, "target SEO asset must be created without waiting for generic daily queue")
            require(len(prepared["generated"]) == 1, "target SEO asset must be generated in same bridge pass")
            require(len(prepared["qc_passed"]) == 1, "target SEO asset must receive deterministic local QC")

            snap = seo_geo_growth.dashboard()
            asset = next(row for row in snap["assets"] if row["id"] == prepared["created"][0])
            require(asset["stage"] == "QC_PASSED", "bridge must stop at QC_PASSED")
            require(not asset.get("public_url"), "bridge must never fake a public URL")
            require(not asset.get("submission_receipts"), "bridge must never fake search receipts")
            require(Path(asset["staging_path"]).is_file(), "target staging page must exist")

            second = bridge.prepare_phase3_assets(plan)
            require(second["targeted"] == 1, "bridge must remain targeted on rerun")
            require(second["created"] == [], "bridge must be idempotent and not duplicate assets")
            require(len([row for row in seo_geo_growth.dashboard()["assets"] if row["opportunity_id"] == opportunity["id"]]) == 1,
                    "Phase3 rerun must not duplicate the SEO asset")

            phase3_patch = (SOURCE / "backend" / "r8_19_geo_phase3_patch.py").read_text(encoding="utf-8")
            require("prepare_phase3_assets" in phase3_patch, "scheduler bridge must prepare Phase3 targets before SEO autonomy")
            require(phase3_patch.index("prepare_phase3_assets") < phase3_patch.index("base = _ORIGINAL_RUN"),
                    "Phase3 target preparation must occur before verified deploy cycle")
            require(phase3_patch.index("base = _ORIGINAL_RUN") < phase3_patch.index("phase3_after = geo_phase3.run_once"),
                    "Phase3 post-sync must occur after verified deploy cycle")

            r820_patch = (SOURCE / "backend" / "r8_20_seo_geo_growth_patch.py").read_text(encoding="utf-8")
            require('path == "/api/r8-13/seo-geo/run"' in r820_patch,
                    "legacy SEO primary run button must be upgraded to the R8-20 full autonomous controller")
            require("result = seo_core.run_once" in r820_patch,
                    "manual growth-cycle route must invoke full autonomy, not local-only run_daily_cycle")

            print(json.dumps({
                "ok": True,
                "target_asset": asset["id"],
                "stage": asset["stage"],
                "truth": "No PUBLISHED/SUBMITTED state is fabricated by the bridge.",
            }, ensure_ascii=False))
        finally:
            if previous is None:
                os.environ.pop("LOCALAPPDATA", None)
            else:
                os.environ["LOCALAPPDATA"] = previous


if __name__ == "__main__":
    main()
