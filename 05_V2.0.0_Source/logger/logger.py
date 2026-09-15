"""
V2.0.0 logging foundation.
"""

from datetime import datetime


class Logger:
    def info(self, message):
        return f"[{datetime.now()}] INFO {message}"

    def error(self, message):
        return f"[{datetime.now()}] ERROR {message}"
