from flask import Flask, jsonify, render_template_string
import time
from config import IFACE, POLL_INTERVAL_SEC, HISTORY_MINUTES
from state import lock, latest_status, latest_clients, client_count_history, recent_events

app = Flask(__name__)

@app.get("/api/clients")
def api_clients():
    with lock:
        data = {
            'ts': int(time.time()),
            'clients': dict(latest_clients),
        }
    return jsonify(data)

@app.get("/api/status")
def api_status():
    with lock:
        status = dict(latest_status)
        status['live_num_sta'] = len(latest_clients)
    return jsonify(status)

@app.get("/api/summary")
def api_summary():
    now = int(time.time())
    with lock:
        connects = sum(1 for e in recent_events if e[1] == 'connected')
        disconnects = sum(1 for e in recent_events if e[1] == 'disconnected')
        hist = list(client_count_history)
        sampled = hist[::max(1, int(60 / POLL_INTERVAL_SEC))]
        summary = {
            'ts': now,
            'connects_24h': connects,
            'disconnects_24h': disconnects,
            'history': sampled,
            'live_num_sta': len(latest_clients),
        }
    return jsonify(summary)

INDEX_HTML = """
<!doctype html>
<!-- ...existing HTML template... -->
"""

@app.get("/")
def index():
    return render_template_string(INDEX_HTML, iface=IFACE, poll=POLL_INTERVAL_SEC, interval=int(POLL_INTERVAL_SEC*1000), history_minutes=HISTORY_MINUTES)
