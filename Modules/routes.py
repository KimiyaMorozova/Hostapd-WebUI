from flask import render_template, jsonify
from Modules import hostapd


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