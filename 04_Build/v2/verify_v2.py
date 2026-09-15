"""Exercise source/frozen HTTP runtime; reject mixed assets and legacy regressions."""
import argparse
import hashlib
import json
import os
import socket
import subprocess
import sys
import tempfile
import time
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
NAME = "Kazuizhi_AI_Enterprise_V2.0.0_Beta"
BUILD = "KZ-ENTERPRISE-V2-BETA-20260915"

def check(condition, message):
    if not condition:
        raise AssertionError(message)

def inspect_source():
    manifest = json.loads((ROOT / "04_Build/v2/r3_preservation.json").read_text(encoding="utf-8"))
    for name, expected in manifest.items():
        check(hashlib.sha256((ROOT / name).read_bytes()).hexdigest() == expected, f"R3/history changed: {name}")
    for base in (ROOT / "05_V2.0.0_Source",):
        for p in base.rglob("*"):
            if p.is_file() and p.suffix not in (".pyc",):
                text = p.read_text(encoding="utf-8")
                if p.suffix not in (".md", ".json"):
                    check(not any(x in text for x in ("1.9.5", "ENTERPRISE-R2", "ENTERPRISE-R3", "8765")), f"Stale runtime identity: {p}")
    workflow = (ROOT / ".github/workflows/build_v2_enterprise_beta.yml").read_text(encoding="utf-8")
    check("03_V1.9.5_Source" not in workflow and "kazuizhi_v1.9.5.spec" not in workflow, "Legacy build dependency")
    check("installer_output_v2/" in workflow, "Setup upload missing")

def exercise(command):
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        port = s.getsockname()[1]
    with tempfile.TemporaryDirectory() as tmp:
        with open(Path(tmp) / "runtime.log", "w+", encoding="utf-8") as log:
            p = subprocess.Popen(command + ["--no-browser", "--port", str(port)], cwd=tmp, stdout=log, stderr=subprocess.STDOUT)
            try:
                base = f"http://127.0.0.1:{port}"
                for attempt in range(100):
                    check(p.poll() is None, "Runtime exited before readiness")
                    try:
                        with urllib.request.urlopen(base + "/api/status", timeout=1) as response:
                            status = json.load(response)
                        break
                    except OSError:
                        time.sleep(.2)
                else:
                    raise AssertionError("Runtime startup timeout")
                check(status["version"] == "2.0.0" and status["stage"] == "Beta" and status["build"] == BUILD, "Wrong API version")
                for path in ("/", "/?build=" + BUILD, "/WEB_VERSION.txt"):
                    with urllib.request.urlopen(base + path) as response:
                        text = response.read().decode("utf-8")
                        check(BUILD in text and "1.9.5" not in text, "Wrong HTTP asset identity")
                        check(response.headers["Cache-Control"] == "no-store", "Cache guard missing")
                for route in ("tasks", "statistics", "kazuizhi"):
                    with urllib.request.urlopen(base + "/api/" + route) as response:
                        check(json.load(response)["status"] == "not_connected", "Placeholder data misreported")
                # A second process must fail, not open a browser to the occupied port.
                duplicate = subprocess.run(command + ["--no-browser", "--port", str(port)], cwd=tmp, env=dict(os.environ, LOCALAPPDATA=tmp), capture_output=True, timeout=15)
                check(duplicate.returncode != 0, "Port conflict accepted")
            finally:
                p.terminate()
                p.wait(timeout=15)
                log.seek(0)
                print(log.read())

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--source", action="store_true")
    group.add_argument("--exe", type=Path)
    args = parser.parse_args()
    inspect_source()
    if args.exe:
        exe = args.exe.resolve()
        check(exe.name == NAME + ".exe", "Wrong executable name")
        resources = exe.parent / "_internal"
        for source_dir in ("web", "version"):
            for source in (ROOT / "05_V2.0.0_Source" / source_dir).rglob("*"):
                if source.is_file():
                    packed = resources / source_dir / source.relative_to(ROOT / "05_V2.0.0_Source" / source_dir)
                    check(packed.read_bytes() == source.read_bytes(), f"Packaged asset mismatch: {packed}")
        exercise([str(exe)])
    else:
        exercise([sys.executable, str(ROOT / "05_V2.0.0_Source/run.py")])
    print("PASS: V2 identity, HTTP routes, resources, port conflict, R3/history preservation")
