#!/usr/bin/env python3
from dotenv import load_dotenv
load_dotenv(override=True)
import signal
import os
import logging
from logging.handlers import RotatingFileHandler
from flask import Flask, render_template, request
from routes import register_routes
from state import IFACE, POLL_INTERVAL_SEC, HISTORY_MINUTES, HOST, PORT

# --- new: logging setup ---
LOG_DIR = os.path.join(os.path.dirname(__file__), "logs")
os.makedirs(LOG_DIR, exist_ok=True)
log_file = os.path.join(LOG_DIR, "app.log")
root_logger = logging.getLogger()
root_logger.setLevel(logging.DEBUG)
fmt = logging.Formatter("%(asctime)s %(levelname)s %(name)s: %(message)s")
# console
ch = logging.StreamHandler()
ch.setFormatter(fmt)
ch.setLevel(logging.DEBUG)
root_logger.addHandler(ch)
# rotating file
fh = RotatingFileHandler(log_file, maxBytes=2_000_000, backupCount=5, encoding="utf-8")
fh.setFormatter(fmt)
fh.setLevel(logging.DEBUG)
root_logger.addHandler(fh)
logging.getLogger("werkzeug").setLevel(logging.INFO)
# --- end logging setup ---

app = Flask(__name__)
# make flask's logger use our handlers
app.logger.handlers = root_logger.handlers
app.logger.setLevel(logging.DEBUG)

register_routes(app)

# log requests
@app.before_request
def _log_request():
    app.logger.debug("HTTP %s %s from %s", request.method, request.path, request.remote_addr)

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
    app.logger.info("Starting Hostapd WebUI on %s:%s (iface=%s)", HOST, PORT, IFACE)
    app.run(host=HOST, port=PORT, debug=False)
