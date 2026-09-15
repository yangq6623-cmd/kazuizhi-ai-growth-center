"""
Kazuizhi AI Growth Center V1.9.5
Main runtime entry
"""

import traceback
import time
import threading
import webbrowser
from pathlib import Path

from core.version import VERSION
from config.config_loader import ConfigLoader
from logger.logger import Logger
from ai_center.ai_engine import AIEngine


def open_dashboard():
    """Open local dashboard after startup."""
    try:
        time.sleep(2)
        webbrowser.open("http://127.0.0.1:8765")
    except Exception:
        pass


def main():
    logger = Logger()
    logger.info(f"Kazuizhi AI V{VERSION} starting")

    config = ConfigLoader()
    config.load()

    ai = AIEngine()
    ai.start()

    logger.info("System startup completed")

    threading.Thread(target=open_dashboard, daemon=True).start()

    while True:
        time.sleep(1)


if __name__ == "__main__":
    try:
        main()
    except Exception:
        error_file = Path("kazuizhi_error.log")
        error_file.write_text(traceback.format_exc(), encoding="utf-8")
        raise
