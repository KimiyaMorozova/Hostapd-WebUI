#!/usr/bin/env python3
import os, signal, time
from flask import Flask, jsonify, render_template
from poller import start_poller, stop_poller, get_status, get_clients, get_summary

HOST = os.getenv("DASHBOARD_HOST", "0.0.0.0")
PORT = int(os.getenv("DASHBOARD_PORT", 8080))
POLL_INTERVAL_SEC = float(os.getenv("POLL_INTERVAL", 5))
HISTORY_MINUTES = int(os.getenv("HISTORY_MINUTES", 120))
IFACE = os.getenv("HOSTAPD_IFACE", "wlan0")

app = Flask(__name__, template_folder="templates")

@app.get("/api/clients")
def api_clients():
    return jsonify({"ts": int(time.time()), "clients": get_clients()})

@app.get("/api/status")
def api_status():
    status = get_status().copy()
    status['live_num_sta'] = len(get_clients())
    return jsonify(status)

@app.get("/api/summary")
def api_summary():
    return jsonify(get_summary())

@app.get("/")
def index():
    return render_template(
        "index.html",
        iface=IFACE,
        poll=POLL_INTERVAL_SEC,
        interval=int(POLL_INTERVAL_SEC * 1000),
        history_minutes=HISTORY_MINUTES
    )

if __name__ == "__main__":
    signal.signal(signal.SIGINT, signal.SIG_DFL)
    start_poller()
    try:
        app.run(host=HOST, port=PORT, debug=False)
    finally:
        stop_poller()
