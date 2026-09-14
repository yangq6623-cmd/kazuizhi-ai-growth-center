"""
Kazuizhi AI Growth Center V1.9.5
Main runtime entry
"""

import traceback
from pathlib import Path

from core.version import VERSION
from config.config_loader import ConfigLoader
from logger.logger import Logger
from ai_center.ai_engine import AIEngine


def main():
    logger = Logger()
    logger.info(f"Kazuizhi AI V{VERSION} starting")

    config = ConfigLoader()
    config.load()

    ai = AIEngine()
    ai.start()

    logger.info("System startup completed")


if __name__ == "__main__":
    try:
        main()
    except Exception:
        error_file = Path("kazuizhi_error.log")
        error_file.write_text(traceback.format_exc(), encoding="utf-8")
        raise
