"""Data layer base for V2.0.0"""

from pathlib import Path

DATA_DIR = Path("data")


def init_data():
    DATA_DIR.mkdir(exist_ok=True)
    return DATA_DIR
