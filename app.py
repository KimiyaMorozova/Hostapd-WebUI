#!/usr/bin/env python3
from dotenv import load_dotenv
load_dotenv(override=True)

#import flask and routes module to load routes from other files
from flask import Flask, render_template 
from Modules import routes, check
import time, sys

import os, threading
host = os.getenv("DASHBOARD_HOST", "0.0.0.0")
port = os.getenv("DASHBOARD_PORT", 5000)
interface = os.getenv("HOSTAPD_IFACE", "wlan0")



def run_server():
    app = Flask(__name__)
    routes.register_routes(app)  # Routen werden hier registriert
    app.run(host=host, port=port, debug=False)




if __name__ == "__main__":
    threading.Thread(target=run_server, daemon=True).start()
    def handle_sigint(sig, frame):
        print("\nBeende Server...")
        sys.exit(0)
    try:
        print("Server läuft. Drücke STRG+C zum Beenden.")
        while True:
            time.sleep(1)  # Hauptthread bleibt "wach"
    except KeyboardInterrupt:
        print("\nBeende Server...")
        sys.exit(0)

