from __future__ import annotations

import argparse
import base64
import json
import os
import socket
import subprocess
import tempfile
import time
import urllib.request
from pathlib import Path


PNG_1X1 = base64.b64encode(
    b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01\x08\x06\x00\x00\x00\x1f\x15\xc4\x89"
).decode("ascii")


def get(url):
    with urllib.request.urlopen(url, timeout=8) as response:
        return response.status, response.read()


def post(url, payload):
    data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    request = urllib.request.Request(url, data=data, headers={"Content-Type": "application/json"}, method="POST")
    with urllib.request.urlopen(request, timeout=30) as response:
        return response.status, json.loads(response.read().decode("utf-8"))


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--exe", required=True)
    args = parser.parse_args()
    exe = Path(args.exe).resolve()
    assert exe.is_file(), exe
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        port = sock.getsockname()[1]
    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as folder:
        env = dict(os.environ, LOCALAPPDATA=folder, PYTHONUTF8="1", PYTHONIOENCODING="utf-8")
        process = subprocess.Popen([str(exe), "--no-browser", "--port", str(port)], env=env)
        base = f"http://127.0.0.1:{port}"
        try:
            for _ in range(120):
                try:
                    if get(base + "/api/status")[0] == 200:
                        break
                except Exception:
                    time.sleep(0.25)
            else:
                raise AssertionError("Packaged app did not become ready")
            status, script = get(base + "/seo-campaign-intake.js")
            assert status == 200 and b"campaign/import" in script and b"campaign-import-run" in script
            payload = {
                "campaign_id": "PACKAGED-R8-32-SMOKE",
                "region": "涟水县", "service": "水电安装维修", "keyword": "涟水水电维修",
                "title": "打包版推广入库验收", "summary": "验证打包后的真实内容入库入口。",
                "content": "## 验收正文\n- 内容已进入本地资产队列\n- 后续阶段仍执行真实回执门槛",
                "image_name": "smoke.png", "image_mime": "image/png", "image_base64": PNG_1X1,
                "rights_confirmed": True, "run_now": False,
            }
            status, reply = post(base + "/api/r8-13/seo-geo/campaign/import", payload)
            assert status == 200, reply
            imported = reply.get("import") or {}
            asset = imported.get("asset") or {}
            assert imported.get("created") is True and asset.get("stage") == "GENERATED", reply
            assert len(asset.get("staging_attachments") or []) == 1, asset
            _, second = post(base + "/api/r8-13/seo-geo/campaign/import", payload)
            assert (second.get("import") or {}).get("idempotent") is True, second
        finally:
            process.terminate()
            try:
                process.wait(timeout=10)
            except subprocess.TimeoutExpired:
                process.kill()
        print("PASS: packaged R8-32 campaign UI + import endpoint + image staging + idempotency")


if __name__ == "__main__":
    main()
