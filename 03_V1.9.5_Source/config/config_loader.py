"""
V1.9.5 configuration loader.
"""

DEFAULT_CONFIG = {
    "version": "1.9.5",
    "environment": "development",
    "data_path": "data"
}


class ConfigLoader:
    def load(self):
        return DEFAULT_CONFIG.copy()
