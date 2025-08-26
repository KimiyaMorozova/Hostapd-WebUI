import time
from flask import jsonify
from state import lock, latest_clients, latest_status, recent_events, client_count_history, POLL_INTERVAL_SEC

def register_routes(app):
    @app.get("/api/clients")
    def api_clients():
        with lock:
            data = {"ts": int(time.time()), "clients": latest_clients}
        return jsonify(data)

    @app.get("/api/status")
    def api_status():
        with lock:
            status = latest_status.copy()
            status["live_num_sta"] = len(latest_clients)
        return jsonify(status)

    @app.get("/api/summary")
    def api_summary():
        now = int(time.time())
        with lock:
            connects = sum(1 for e in recent_events if e[1] == "connected")
            disconnects = sum(1 for e in recent_events if e[1] == "disconnected")
            hist = list(client_count_history)
            sampled = hist[::max(1,int(60/POLL_INTERVAL_SEC))]
            summary = {
                "ts": now,
                "connects_24h": connects,
                "disconnects_24h": disconnects,
                "history": sampled,
                "live_num_sta": len(latest_clients),
            }
        return jsonify(summary)
