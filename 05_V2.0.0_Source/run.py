"""Kazuizhi AI Enterprise V2.0.0 Beta entry point."""
import argparse
import os
import tempfile
import traceback
import webbrowser
from pathlib import Path
from core.version import BUILD_ID, PRODUCT_NAME
from ai_center.ai_engine import AIEngine
from backend.server import create_server

def main():
    parser = argparse.ArgumentParser(description=PRODUCT_NAME)
    parser.add_argument("--port", type=int, default=8876)
    parser.add_argument("--no-browser", action="store_true")
    args = parser.parse_args()
    with create_server(args.port) as server:
        AIEngine().start()
        url = f"http://127.0.0.1:{server.server_port}/?build={BUILD_ID}"
        print(PRODUCT_NAME, flush=True)
        print(f"Dashboard URL: {url}", flush=True)
        if not args.no_browser:
            webbrowser.open(url)
        server.serve_forever()

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        pass
    except Exception:
        error = traceback.format_exc()
        print(error, flush=True)
        logs = Path(os.environ.get("LOCALAPPDATA", tempfile.gettempdir())) / "Kazuizhi_AI_Enterprise_V2.0.0_Beta" / "logs"
        logs.mkdir(parents=True, exist_ok=True)
        (logs / "startup-error.log").write_text(error, encoding="utf-8")
        raise
