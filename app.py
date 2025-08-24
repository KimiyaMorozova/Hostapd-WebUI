from flask import Flask, render_template, jsonify
import subprocess, re, time

app = Flask(__name__)

# --- Hostapd Abfrage ---
def get_connected_clients():
    clients = []
    try:
        result = subprocess.check_output(["hostapd_cli", "-i", "wlan0", "all_sta"], text=True)
        blocks = result.strip().split("\n\n")
        for block in blocks:
            lines = block.split("\n")
            if not lines or not re.match(r"^[0-9a-f]{2}(:[0-9a-f]{2}){5}$", lines[0], re.I):
                continue
            mac = lines[0]
            info = {"mac": mac}
            for line in lines[1:]:
                if "=" in line:
                    k, v = line.split("=", 1)
                    info[k.strip()] = v.strip()
            clients.append(info)
    except Exception as e:
        print("Fehler:", e)
    return clients

@app.route("/")
def index():
    return render_template("index.html")

@app.route("/api/clients")
def api_clients():
    return jsonify(get_connected_clients())

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)
