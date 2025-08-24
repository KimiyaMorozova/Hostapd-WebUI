#!/usr/bin/env python3
"""
Hostapd Dashboard – single-file Flask app

Features
- Reads live station data via `hostapd_cli -i <iface> all_sta`
- Gets AP status via `hostapd_cli -i <iface> status`
- Parses recent hostapd/syslog lines for connect/disconnect events
- Simple dashboard with live-updating tables & charts (no DB needed)
- Works on a "dumb AP" (no DHCP/DNS on the box)

Dependencies
- Python 3.9+
- Flask (pip install flask)
- hostapd_cli available and the Flask process has permission to read the control socket

Run
  export HOSTAPD_IFACE=wlan0   # or your interface
  export HOSTAPD_LOG=/var/log/hostapd.log  # optional; comma-separated list supported
  python3 hostapd_dashboard.py
Then open http://0.0.0.0:8080

Security
- Intended for LAN/admin use. Bind to 127.0.0.1 and reverse-proxy if exposed. No auth included.
"""
import os
import re
import json
import time
import queue
import math
import shlex
import atexit
import signal
import threading
import subprocess
from datetime import datetime, timedelta
from collections import defaultdict, deque

from flask import Flask, jsonify, request, Response, send_from_directory

# ---------------------- Configuration ----------------------
HOST = os.getenv("DASHBOARD_HOST", "0.0.0.0")
PORT = int(os.getenv("DASHBOARD_PORT", 8080))
IFACE = os.getenv("HOSTAPD_IFACE", "wlan0")
HOSTAPD_CLI = os.getenv("HOSTAPD_CLI", "/usr/sbin/hostapd_cli")
LOG_PATHS = [p for p in os.getenv("HOSTAPD_LOG", "/var/log/hostapd.log,/var/log/syslog").split(";") for p in p.split(",")]
LOG_PATHS = [p.strip() for p in LOG_PATHS if p.strip()]
MAX_LOG_SCAN_LINES = int(os.getenv("MAX_LOG_LINES", 5000))
POLL_INTERVAL_SEC = float(os.getenv("POLL_INTERVAL", 5))
HISTORY_MINUTES = int(os.getenv("HISTORY_MINUTES", 120))  # for client-count chart

# ---------------------- State ----------------------
lock = threading.Lock()
latest_status = {}
latest_clients = {}
# history of (timestamp, client_count)
client_count_history = deque(maxlen=HISTORY_MINUTES * max(1, int(60 / POLL_INTERVAL_SEC)))
# simple event counters in last 24h
recent_events = deque(maxlen=20000)  # list of (ts, type, mac)

stop_event = threading.Event()

# ---------------------- Helpers ----------------------


# ---------------------- Poller Thread ----------------------

def poller():
    while not stop_event.is_set():
        # hostapd status
        status_text = run_cmd([HOSTAPD_CLI, '-i', IFACE, 'status'])
        status = parse_hostapd_status(status_text) if status_text else {}

        # clients
        sta_text = run_cmd([HOSTAPD_CLI, '-i', IFACE, 'all_sta'])
        clients = parse_all_sta(sta_text) if sta_text else {}

        # logs (recent)
        ev = scan_logs(LOG_PATHS, MAX_LOG_SCAN_LINES)

        with lock:
            global latest_status, latest_clients
            latest_status = status
            latest_clients = clients
            # update client count history
            ts = int(time.time())
            client_count_history.append((ts, len(clients)))
            # update recent events
            # keep only last 24h window
            now = time.time()
            while recent_events and recent_events[0][0] < now - 24*3600:
                recent_events.popleft()
            for e in ev:
                recent_events.append(e)
        time.sleep(POLL_INTERVAL_SEC)


bg = threading.Thread(target=poller, daemon=True)
bg.start()

@atexit.register
def _cleanup():
    stop_event.set()
    try:
        bg.join(timeout=1)
    except Exception:
        pass

# ---------------------- Web ----------------------
app = Flask(__name__, static_folder="static")


@app.get("/api/clients")
def api_clients():
    with lock:
        data = {
            'ts': int(time.time()),
            'clients': latest_clients,
        }
    return jsonify(data)


@app.get("/api/status")
def api_status():
    with lock:
        status = latest_status.copy()
        # enrich with live count
        status['live_num_sta'] = len(latest_clients)
    return jsonify(status)


@app.get("/api/summary")
def api_summary():
    now = int(time.time())
    with lock:
        # events in last 24h
        connects = sum(1 for e in recent_events if e[1] == 'connected')
        disconnects = sum(1 for e in recent_events if e[1] == 'disconnected')
        # history lists
        hist = list(client_count_history)
        # sample every ~minute for chart simplicity
        sampled = hist[::max(1, int(60 / POLL_INTERVAL_SEC))]
        summary = {
            'ts': now,
            'connects_24h': connects,
            'disconnects_24h': disconnects,
            'history': sampled,
            'live_num_sta': len(latest_clients),
        }
    return jsonify(summary)


@app.get("/")
def index():
    return send_from_directory("static", "index.html")


@app.get("/static/<path:filename>")
def static_files(filename):
    return send_from_directory("static", filename)


# ---------------------- Entrypoint ----------------------
if __name__ == "__main__":
    # allow Ctrl+C
    signal.signal(signal.SIGINT, signal.SIG_DFL)
    app.run(host=HOST, port=PORT, debug=False)