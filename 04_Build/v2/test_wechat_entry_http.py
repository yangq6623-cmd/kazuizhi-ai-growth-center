import json
import sys
import threading
import urllib.request
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
SOURCE = ROOT / "05_V2.0.0_Source"
sys.path.insert(0, str(SOURCE))

from backend.server import create_server


def get_json(url):
    with urllib.request.urlopen(url, timeout=5) as response:
        return json.load(response)


def main():
    server = create_server(0)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        base = f"http://127.0.0.1:{server.server_port}"
        entry = get_json(base + "/api/wechat-mini-program/entry")
        status = get_json(base + "/api/wechat-mini-program/status")
        with urllib.request.urlopen(base + "/analytics.js", timeout=5) as response:
            javascript = response.read().decode("utf-8")
        assert entry["identity"]["app_id"] == "wxcc5ca2cefb937dba"
        assert entry["identity"]["original_id"] == "gh_81812d9605fa"
        assert entry["identity"]["default_path"] == "pages/index/index"
        assert entry["secret_exposed"] is False
        assert "entry" in status
        assert "生成官网小程序直达链接" in javascript
        assert "/api/wechat-mini-program/url-link" in javascript
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=3)
    print("PASS: WeChat public entry API and local-only URL Link UI contract verified")


if __name__ == "__main__":
    main()
