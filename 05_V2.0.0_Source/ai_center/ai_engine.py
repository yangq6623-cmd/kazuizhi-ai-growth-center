"""Engine lifecycle scaffold; automation providers are not connected yet."""
from core.version import VERSION

class AIEngine:
    def __init__(self):
        self.version = VERSION
        self.status = "initialized"
        self.url = None

    def start(self):
        # The launcher owns the sole HTTP server and browser window.
        self.status = "ready"
        return self.status

    def health_check(self):
        return {"version": self.version, "status": self.status, "url": self.url}
