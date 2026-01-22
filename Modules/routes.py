from flask import render_template, jsonify
from Modules import hostapd
from datetime import datetime, timedelta
import time
import threading
import os
import subprocess

history = []
device_history = {}  # mac -> list of {time, signal, tx_packets, rx_packets}
poll_interval = int(os.getenv("POLL_INTERVAL", 5))

def update_history():
    while True:
        devices = hostapd.get_connected_devices()
        device_details = []
        current_time = datetime.now().isoformat()
        for mac in devices:
            info = hostapd.get_device_info(mac)
            if info:
                signal = int(info.get("signal", 0))
                tx_packets = int(info.get("tx_packets", 0))
                rx_packets = int(info.get("rx_packets", 0))
                device_details.append({
                    "mac": mac,
                    "signal": signal,
                    "tx_packets": tx_packets,
                    "rx_packets": rx_packets
                })
                # Update device history
                if mac not in device_history:
                    device_history[mac] = []
                device_history[mac].append({
                    "time": current_time,
                    "signal": signal,
                    "tx_packets": tx_packets,
                    "rx_packets": rx_packets
                })
                # Keep only last 120 min
                cutoff = datetime.now() - timedelta(minutes=120)
                device_history[mac] = [h for h in device_history[mac] if datetime.fromisoformat(h["time"]) > cutoff]
        
        count = len(devices)
        history.append({
            "time": current_time,
            "clients": count,
            "devices": device_details
        })
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

    @app.get("/api/signal_history")
    def signal_history():
        data = []
        for h in history:
            avg_signal = 0
            if h["devices"]:
                avg_signal = sum(d["signal"] for d in h["devices"]) / len(h["devices"])
            data.append({"time": h["time"], "avg_signal": avg_signal})
        return jsonify(data)

    @app.get("/api/bandwidth_history")
    def bandwidth_history():
        data = []
        prev_tx = 0
        prev_rx = 0
        prev_time = None
        for h in history:
            current_time = datetime.fromisoformat(h["time"])
            total_tx = sum(d["tx_packets"] for d in h["devices"])
            total_rx = sum(d["rx_packets"] for d in h["devices"])
            if prev_time:
                time_diff = (current_time - prev_time).total_seconds()
                tx_rate = (total_tx - prev_tx) / time_diff if time_diff > 0 else 0
                rx_rate = (total_rx - prev_rx) / time_diff if time_diff > 0 else 0
            else:
                tx_rate = 0
                rx_rate = 0
            data.append({"time": h["time"], "tx_rate": tx_rate, "rx_rate": rx_rate})
            prev_tx = total_tx
            prev_rx = total_rx
            prev_time = current_time
        return jsonify(data)

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