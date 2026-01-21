from flask import render_template, jsonify
from Modules import hostapd
from datetime import datetime, timedelta
import time
import threading
import os
import subprocess

history = []
poll_interval = int(os.getenv("POLL_INTERVAL", 5))

def update_history():
    while True:
        count = len(hostapd.get_connected_devices())
        history.append({"time": datetime.now().isoformat(), "clients": count})
        # Alte Einträge entfernen, älter als 120 min
        cutoff = datetime.now() - timedelta(minutes=120)
        history[:] = [h for h in history if datetime.fromisoformat(h["time"]) > cutoff]
        time.sleep(poll_interval)

def register_routes(app):
    @app.get("/")
    def index():
        return render_template("index.html")

    @app.get("/api/hello")
    def hello():
        return jsonify({"message": "Hallo von der API!"})
    
    @app.get("/api/status")
    def status():
        return jsonify(hostapd.hostapd_status())

    @app.get("/api/devices")
    def devices():
        return jsonify(hostapd.get_connected_devices())

    @app.get("/api/device/<mac>")
    def device(mac):
        return jsonify(hostapd.get_device_info(mac))

    @app.get("/api/clients")
    def clients():
        return jsonify(history)

    @app.get("/api/events")
    def events():
        return jsonify(hostapd.get_24h_events())

    @app.post("/api/hostapd/<action>")
    def control_hostapd(action):
        if action not in ['stop', 'start', 'restart']:
            return jsonify({"error": "Invalid action"}), 400
        try:
            subprocess.run(['sudo', 'systemctl', action, 'hostapd'], check=True)
            return jsonify({"status": f"hostapd {action}ed"})
        except subprocess.CalledProcessError as e:
            return jsonify({"error": str(e)}), 500