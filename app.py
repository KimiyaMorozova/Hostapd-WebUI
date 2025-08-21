#!/usr/bin/env python3
from flask import Flask
import signal
import atexit

from config import HOST, PORT
from poller import start_poller, stop_poller
import routes

app = routes.app

if __name__ == "__main__":
    # allow Ctrl+C
    signal.signal(signal.SIGINT, signal.SIG_DFL)
    start_poller()
    atexit.register(stop_poller)
    app.run(host=HOST, port=PORT, debug=False)