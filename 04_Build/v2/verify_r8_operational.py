"""End-to-end acceptance test for V2.2 R8 Operational source/frozen runtime."""

import argparse
import json
import os
import socket
import subprocess
import sys
import tempfile
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
NAME = "Kazuizhi_AI_Enterprise_V2.0.0_Beta"
BUILD = "KZ-ENTERPRISE-V2.2-R8-OPERATIONAL-20260920"


def check(value, message):
    if not value:
        raise AssertionError(message)


def source_checks():
    source = ROOT / "05_V2.0.0_Source"
    html = (source / "web/operational.html").read_text(encoding="utf-8")
    r7_html = (source / "web/index.html").read_text(encoding="utf-8")
    r7_app = (source / "web/app.js").read_text(encoding="utf-8")
    check(BUILD in html, "Operational UI build identity missing")
    for label in ("今天让什么结果发生", "增长战役", "内容工厂", "手机与真机", "账号与发布", "咨询与订单", "SEO 与 GEO", "连接与体检"):
        check(label in html, f"Operational page missing: {label}")
    check("返回 R7 完整总控制台" in html and "/index.html" in html, "Operational workspace cannot return to R7")
    for label in ("AI 指挥中心", "任务与员工", "今日复盘", "经营分析", "内容增长", "市场洞察", "任务日历", "运营总结", "明日计划", "历史记录", "运营记忆"):
        check(label in r7_html, f"R7 primary console module missing: {label}")
    check("内容生产与发布" in r7_app and "operational-hub" in r7_app and "/operational.html?embedded=1" in r7_app, "R7 console is missing the merged V2.2 workspace")
    pyramid = (source / "web/r8_command_pyramid.js").read_text(encoding="utf-8")
    check("'operational-hub'" in pyramid, "Merged V2.2 workspace is missing from the R7/R8 navigation pyramid")
    server = (source / "backend/server.py").read_text(encoding="utf-8")
    for route in ("/api/content-factory/assets/upload", "/api/video-worker/render", "/api/r8/device/screenshot"):
        check(route in server, f"Required API missing: {route}")
    patch = (source / "backend/content_factory_patch.py").read_text(encoding="utf-8")
    check("/api/content-factory/chatgpt-plan" in patch and "/api/content-factory/candidate-file" in patch,
          "ChatGPT plan or final video review route missing")
    contract = (source / "promotion/production_contract.py").read_text(encoding="utf-8")
    check("kazuizhi-content-production/v1" in contract and "missing_material_must_not_block" in contract,
          "ChatGPT production contract missing")
    worker = (source / "promotion/video_worker.py").read_text(encoding="utf-8")
    check("h264_nvenc" in worker and "libx264" in worker and "run_pending" in worker,
          "GPU/CPU automatic video queue missing")
    spec = (ROOT / "04_Build/kazuizhi_v2.0.0.spec").read_text(encoding="utf-8")
    check("console=False" in spec and "imageio_ffmpeg" in spec, "Packaged video runtime missing")


def http_json(base, path, payload=None):
    data = None
    headers = {}
    method = "GET"
    if payload is not None:
        method = "POST"
        data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        headers["Content-Type"] = "application/json"
    request = urllib.request.Request(base + path, data=data, headers=headers, method=method)
    with urllib.request.urlopen(request, timeout=30) as response:
        return response.status, json.load(response)


def exercise(command):
    with socket.socket() as probe:
        probe.bind(("127.0.0.1", 0))
        port = probe.getsockname()[1]
    with tempfile.TemporaryDirectory() as temporary:
        env = dict(os.environ, LOCALAPPDATA=temporary)
        log_path = Path(temporary) / "runtime.log"
        with log_path.open("w+", encoding="utf-8") as log:
            process = subprocess.Popen(command + ["--no-browser", "--port", str(port)], cwd=temporary, env=env, stdout=log, stderr=subprocess.STDOUT)
            try:
                base = f"http://127.0.0.1:{port}"
                for _ in range(120):
                    check(process.poll() is None, "Runtime exited before readiness")
                    try:
                        _, status = http_json(base, "/api/status")
                        break
                    except OSError:
                        time.sleep(.2)
                else:
                    raise AssertionError("Runtime startup timeout")
                check(status["version"] == "2.2.0" and status["stage"] == "Operational" and status["build"] == BUILD, "Wrong runtime identity")
                with urllib.request.urlopen(base + "/", timeout=10) as response:
                    root_html = response.read().decode("utf-8")
                    check(BUILD in root_html and "AI 指挥中心" in root_html and "运营记忆" in root_html, "Root did not serve the complete R7 console")
                    check(response.headers["Cache-Control"] == "no-store", "Cache protection missing")
                with urllib.request.urlopen(base + "/operational.html", timeout=10) as response:
                    operational_html = response.read().decode("utf-8")
                    check(BUILD in operational_html and "今天让什么结果发生" in operational_html, "Additive operational workspace is unavailable")
                for asset in ("operational.css", "operational-device.css", "operational-video.css", "operational.js", "operational-factory.js", "operational-device.js"):
                    with urllib.request.urlopen(base + "/" + asset, timeout=10) as response:
                        check(response.status == 200 and len(response.read()) > 100, f"Packaged UI asset missing: {asset}")

                _, campaign = http_json(base, "/api/content-factory/campaigns", {
                    "region": "涟水县", "service": "家电安装维修",
                    "title": "空调不制冷先检查什么", "evidence": "真实客服高频问题",
                    "goal": "获得可追溯的本地咨询",
                })

                # Critical R8 V2 rule: owner local material is optional. A production
                # request must be accepted with zero uploaded assets and no manual script.
                _, video = http_json(base, "/api/content-factory/videos", {
                    "campaign_id": campaign["id"],
                    "cta": "通过小程序提交需求，等待师傅报价",
                })
                check(video["status"] == "等待ChatGPT策划", "No-asset request did not enter ChatGPT planning state")
                check(video.get("asset_ids") == [], "No-asset request unexpectedly requires owner material")

                plan = {
                    "schema": "kazuizhi-content-production/v1",
                    "version": 1,
                    "campaign_id": campaign["id"],
                    "objective": "获得可追溯的本地咨询",
                    "target_platforms": ["抖音", "视频号"],
                    "topic": "空调不制冷先检查什么",
                    "pain_point": "用户担心一上门就被要求加氟或产生不透明费用",
                    "titles": ["空调不制冷，先别急着加氟"],
                    "script": "空调不制冷时，先看滤网、外机和运行状态，再由师傅现场检测后判断原因。真实维修过程以现场素材为准。",
                    "storyboard": [
                        {
                            "shot_id": "S01", "purpose": "提出用户痛点", "duration_seconds": 3,
                            "subtitle": "空调不制冷，一定就是缺氟吗？",
                            "source_preference": ["local_real", "ai_generated", "info_card"],
                        },
                        {
                            "shot_id": "S02", "purpose": "解释真实检测原则", "duration_seconds": 4,
                            "subtitle": "先检查，再检测，最后判断故障原因",
                            "required_real": True,
                            "source_preference": ["local_real", "info_card"],
                        },
                    ],
                    "cta": "通过小程序提交需求，等待师傅报价",
                    "output": {"width": 1080, "height": 1920, "fps": 30, "duration_seconds": 12},
                }
                _, planned = http_json(base, "/api/content-factory/chatgpt-plan", {
                    "video_id": video["id"], "campaign_id": campaign["id"], "production_plan": plan,
                })
                check(planned["status"] in {"等待生产", "生产中"}, "ChatGPT production contract did not enter local queue")

                _, worker = http_json(base, "/api/video-worker")
                check(worker["ffmpeg_found"] and worker["encoder"] in {"h264_nvenc", "libx264"}, "Packaged FFmpeg worker unavailable")

                # The independent video worker should pick the job automatically. No
                # owner click is allowed between ChatGPT plan and FINAL.MP4.
                final_video = None
                for _ in range(120):
                    _, factory = http_json(base, "/api/content-factory")
                    current = next(x for x in factory["videos"] if x["id"] == video["id"])
                    if current["status"] == "等待人工审核":
                        final_video = current
                        break
                    if current["status"] == "异常待处理":
                        raise AssertionError(f"Automatic video production failed: {current.get('last_error')}")
                    time.sleep(1)
                check(final_video is not None, "Automatic no-asset production did not reach owner review")
                candidate = next((x for x in final_video.get("candidates", []) if x.get("exists")), None)
                check(candidate and candidate.get("technical_qc", {}).get("passed"), "FINAL.MP4 technical QC failed")
                check(all(x.get("source") != "ai_generated" for x in candidate.get("source_summary", [])),
                      "Missing real material was silently represented as generated real footage")
                preview = f"/api/content-factory/candidate-file?video_id={urllib.parse.quote(video['id'])}&candidate_id={urllib.parse.quote(candidate['id'])}"
                with urllib.request.urlopen(base + preview, timeout=30) as response:
                    final_bytes = response.read()
                    check(response.headers.get_content_type() == "video/mp4" and len(final_bytes) > 10 * 1024,
                          "Final review video route did not return a playable MP4 payload")

                # Owner material remains an optional enrichment source and may be added
                # at any time without changing the production prerequisite.
                material = b"\x89PNG\r\n\x1a\n" + b"optional-r8-test-material"
                headers = {
                    "Content-Type": "application/octet-stream",
                    "X-Campaign-ID": urllib.parse.quote(campaign["id"]),
                    "X-Asset-Kind": urllib.parse.quote("真实现场照片"),
                    "X-Filename": urllib.parse.quote("现场照片.png"),
                    "X-Consent-Confirmed": "true",
                }
                request = urllib.request.Request(base + "/api/content-factory/assets/upload", data=material, headers=headers, method="POST")
                with urllib.request.urlopen(request, timeout=20) as response:
                    asset = json.load(response)
                check(asset["exists"] and Path(asset["local_path"]).is_file(), "Optional material intake failed")

                _, device = http_json(base, "/api/r8/device/status")
                if "status" in device:
                    check(device["status"] in {"online", "waiting_device", "adb_error", "missing_adb"}, "Device state is not truthful")
                else:
                    check(isinstance(device.get("adb"), dict) and isinstance(device.get("devices"), list) and device.get("message"), "Inherited #238 device state is not truthful")
                try:
                    http_json(base, "/api/content-factory/review", {"video_id": video["id"], "decision": "确认发布", "candidate_id": "missing"})
                    raise AssertionError("Review bypassed missing real output")
                except urllib.error.HTTPError as error:
                    check(error.code == 400, "Review gate returned wrong status")
                _, factory = http_json(base, "/api/content-factory")
                check(len(factory["campaigns"]) == 1 and len(factory["assets"]) == 1 and len(factory["videos"]) == 1, "Content supply chain persistence failed")
                data_root = Path(temporary) / "Kazuizhi_AI_Enterprise_V2.0.0_Beta" / "data"
                check((data_root / "r8/migration_v2_2.json").is_file(), "R8 migration marker missing")
                migration = json.loads((data_root / "r8/migration_v2_2.json").read_text(encoding="utf-8"))
                check(migration["result"] == "complete", "R8 data backup did not complete")
                duplicate = subprocess.run(command + ["--no-browser", "--port", str(port)], cwd=temporary, env=env, capture_output=True, timeout=15)
                check(duplicate.returncode != 0, "Second runtime accepted occupied port")
            finally:
                process.terminate()
                process.wait(timeout=15)
                log.seek(0)
                print(log.read())


def main():
    parser = argparse.ArgumentParser()
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--source", action="store_true")
    group.add_argument("--exe", type=Path)
    args = parser.parse_args()
    source_checks()
    if args.exe:
        exe = args.exe.resolve()
        check(exe.name == NAME + ".exe", "Wrong packaged executable name")
        internal = exe.parent / "_internal"
        for folder in ("web", "version"):
            for source in (ROOT / "05_V2.0.0_Source" / folder).rglob("*"):
                if source.is_file():
                    packed = internal / folder / source.relative_to(ROOT / "05_V2.0.0_Source" / folder)
                    check(packed.is_file() and packed.read_bytes() == source.read_bytes(), f"Packaged asset mismatch: {source.name}")
        exercise([str(exe)])
    else:
        exercise([sys.executable, str(ROOT / "05_V2.0.0_Source/run.py")])
    print("PASS: R8 ChatGPT contract -> automatic local execution -> FINAL.MP4 -> owner review gate")


if __name__ == "__main__":
    main()