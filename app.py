#!/usr/bin/env python3
from dotenv import load_dotenv
load_dotenv(override=True)
import signal
from flask import Flask, render_template
from routes import register_routes
from state import IFACE, POLL_INTERVAL_SEC, HISTORY_MINUTES, HOST, PORT


app = Flask(__name__)
register_routes(app)

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
    app.run(host=HOST, port=PORT, debug=False)
