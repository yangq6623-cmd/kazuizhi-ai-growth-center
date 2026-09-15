"""
Kazuizhi AI Growth Center V1.9.5
Main runtime entry
"""

import traceback
import time
import threading
import webbrowser
import socket

from core.version import VERSION
from config.config_loader import ConfigLoader
from logger.logger import Logger
from ai_center.ai_engine import AIEngine
from dashboard_server import start_dashboard_server


DASHBOARD_URL = "http://127.0.0.1:8765"


def wait_dashboard_ready(host="127.0.0.1", port=8765, timeout=30):
    start = time.time()
    while time.time() - start < timeout:
        try:
            with socket.create_connection((host, port), timeout=1):
                return True
        except Exception:
            time.sleep(1)
    return False


def open_dashboard():
    try:
        if wait_dashboard_ready():
            webbrowser.open(DASHBOARD_URL)
    except Exception:
        pass


def main():
    logger = Logger()
    logger.info(f"Kazuizhi AI V{VERSION} starting")

    ConfigLoader().load()

    ai = AIEngine()
    ai.start()

    threading.Thread(target=start_dashboard_server, daemon=True).start()
    threading.Thread(target=open_dashboard, daemon=True).start()

    logger.info("System startup completed")

    while True:
        time.sleep(1)


if __name__ == "__main__":
    try:
        main()
    except Exception:
        with open("kazuizhi_error.log", "w", encoding="utf-8") as f:
            f.write(traceback.format_exc())
        raise
