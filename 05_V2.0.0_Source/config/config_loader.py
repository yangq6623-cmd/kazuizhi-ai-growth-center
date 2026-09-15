"""
V2.0.0 configuration loader.
"""

DEFAULT_CONFIG = {
    "version": "2.0.0",
    "environment": "development",
    "data_path": "data"
}


class ConfigLoader:
    def load(self):
        return DEFAULT_CONFIG.copy()
