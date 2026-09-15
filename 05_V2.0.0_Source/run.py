"""Kazuizhi AI Enterprise V2.0.0 Beta entry point."""
import argparse
import ctypes
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
    try:
        server = create_server(args.port)
    except OSError:
        console_message = (
            f"Port {args.port} is occupied by another Kazuizhi runtime. "
            "Close the old Enterprise R2/R3 window and start V2.0.0 Beta R2 again."
        )
        message = (
            f"\u7aef\u53e3 {args.port} \u6b63\u88ab\u65e7\u7248\u5361\u5634\u5b50\u7a0b\u5e8f\u5360\u7528\u3002\n\n"
            "\u8bf7\u5173\u95ed Enterprise R2/R3 \u9ed1\u8272\u8fd0\u884c\u7a97\u53e3\uff0c\u518d\u91cd\u65b0\u542f\u52a8 V2.0.0 Beta R2\u3002"
        )
        print(console_message, flush=True)
        if not args.no_browser and os.name == "nt":
            ctypes.windll.user32.MessageBoxW(0, message, "Kazuizhi AI V2 Beta R2", 0x30)
        raise SystemExit(2)
    with server:
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
