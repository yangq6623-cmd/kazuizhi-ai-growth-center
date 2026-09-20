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
    check(BUILD in html, "Operational UI build identity missing")
    for label in ("今天让什么结果发生", "增长战役", "内容工厂", "手机与真机", "账号与发布", "咨询与订单", "SEO 与 GEO", "连接与体检"):
        check(label in html, f"Operational page missing: {label}")
    server = (source / "backend/server.py").read_text(encoding="utf-8")
    for route in ("/api/content-factory/assets/upload", "/api/video-worker/render", "/api/r8/device/screenshot"):
        check(route in server, f"Required API missing: {route}")
    worker = (source / "promotion/video_worker.py").read_text(encoding="utf-8")
    check("h264_nvenc" in worker and "libx264" in worker, "GPU/CPU video encoding fallback missing")
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
                    check(BUILD in root_html and "今天让什么结果发生" in root_html, "Root did not serve operational console")
                    check(response.headers["Cache-Control"] == "no-store", "Cache protection missing")
                for asset in ("operational.css", "operational-device.css", "operational-video.css", "operational.js", "operational-factory.js", "operational-device.js"):
                    with urllib.request.urlopen(base + "/" + asset, timeout=10) as response:
                        check(response.status == 200 and len(response.read()) > 100, f"Packaged UI asset missing: {asset}")

                _, campaign = http_json(base, "/api/content-factory/campaigns", {
                    "region": "涟水县", "service": "家电安装维修",
                    "title": "空调不制冷先检查什么", "evidence": "真实客服高频问题",
                    "goal": "获得可追溯的本地咨询",
                })
                material = b"\x89PNG\r\n\x1a\n" + b"r8-test-material"
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
                check(asset["exists"] and Path(asset["local_path"]).is_file(), "Managed asset upload failed")
                _, video = http_json(base, "/api/content-factory/videos", {
                    "campaign_id": campaign["id"],
                    "script": "先检查滤网和外机状态，再由师傅现场判断。",
                    "duration_target": 10, "cta": "通过小程序提交需求，等待师傅报价",
                })
                check(video["status"] == "等待生产", "Video did not enter production queue")
                _, worker = http_json(base, "/api/video-worker")
                check(worker["ffmpeg_found"] and worker["encoder"] in {"h264_nvenc", "libx264"}, "Packaged FFmpeg worker unavailable")
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
    print("PASS: V2.2 R8 Operational identity, migration, content, device, video and approval gates")


if __name__ == "__main__":
    main()
