"""Compatibility entry routed to the V2 dashboard (no legacy HTML server)."""
from backend.server import create_server

def start_web():
    import threading
    server = create_server()
    threading.Thread(target=server.serve_forever, daemon=True).start()
    return "http://127.0.0.1:8876/"
