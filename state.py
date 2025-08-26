import os, threading, collections

# ---------------------- Configuration ----------------------
HOST = os.getenv("DASHBOARD_HOST", "0.0.0.0")
PORT = int(os.getenv("DASHBOARD_PORT", 8080))
IFACE = os.getenv("HOSTAPD_IFACE", "wlan0")
HOSTAPD_CLI = os.getenv("HOSTAPD_CLI", "/usr/sbin/hostapd_cli")
LOG_PATHS = [p for p in os.getenv("HOSTAPD_LOG", "/var/log/hostapd.log,/var/log/syslog").split(";") for p in p.split(",")]
LOG_PATHS = [p.strip() for p in LOG_PATHS if p.strip()]
MAX_LOG_SCAN_LINES = int(os.getenv("MAX_LOG_LINES", 5000))
POLL_INTERVAL_SEC = float(os.getenv("POLL_INTERVAL", 5))
HISTORY_MINUTES = int(os.getenv("HISTORY_MINUTES", 120))

# ---------------------- State ----------------------
lock = threading.Lock()
latest_status = {}
latest_clients = {}
client_count_history = collections.deque(maxlen=HISTORY_MINUTES * max(1, int(60 / POLL_INTERVAL_SEC)))
recent_events = collections.deque(maxlen=20000)

stop_event = threading.Event()
