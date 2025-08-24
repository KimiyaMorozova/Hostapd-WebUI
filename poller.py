import os, time, threading, subprocess
from collections import deque
from parsers import parse_hostapd_status, parse_all_sta, scan_logs

HOSTAPD_CLI = os.getenv("HOSTAPD_CLI", "/usr/sbin/hostapd_cli")
IFACE = os.getenv("HOSTAPD_IFACE", "wlan0")
LOG_PATHS = [p.strip() for part in os.getenv(
    "HOSTAPD_LOG", "/var/log/hostapd.log,/var/log/syslog"
).split(";") for p in part.split(",") if p.strip()]
POLL_INTERVAL_SEC = float(os.getenv("POLL_INTERVAL", 5))
HISTORY_MINUTES = int(os.getenv("HISTORY_MINUTES", 120))
MAX_LOG_SCAN_LINES = int(os.getenv("MAX_LOG_LINES", 5000))

_lock = threading.Lock()
_stop = threading.Event()
_thread = None

latest_status = {}
latest_clients = {}
client_count_history = deque(maxlen=HISTORY_MINUTES * max(1, int(60 / POLL_INTERVAL_SEC)))
recent_events = deque(maxlen=20000)  # list of (ts, type, mac)

def run_cmd(cmd, timeout=5):
    try:
        out = subprocess.check_output(cmd, stderr=subprocess.STDOUT, timeout=timeout)
        return out.decode(errors="ignore")
    except Exception:
        return ""

def _poller():
    while not _stop.is_set():
        status_text = run_cmd([HOSTAPD_CLI, "-i", IFACE, "status"])
        sta_text = run_cmd([HOSTAPD_CLI, "-i", IFACE, "all_sta"])
        status = parse_hostapd_status(status_text) if status_text else {}
        clients = parse_all_sta(sta_text) if sta_text else {}
        ev = scan_logs(LOG_PATHS, MAX_LOG_SCAN_LINES)

        with _lock:
            global latest_status, latest_clients
            latest_status = status
            latest_clients = clients
            ts = int(time.time())
            client_count_history.append((ts, len(clients)))
            now = time.time()
            while recent_events and recent_events[0][0] < now - 24*3600:
                recent_events.popleft()
            for e in ev:
                recent_events.append(e)
        time.sleep(POLL_INTERVAL_SEC)

def start_poller():
    global _thread
    _stop.clear()
    _thread = threading.Thread(target=_poller, daemon=True)
    _thread.start()

def stop_poller():
    _stop.set()
    if _thread:
        _thread.join(timeout=1)

def get_status():
    with _lock:
        return latest_status.copy()

def get_clients():
    with _lock:
        return latest_clients.copy()

def get_summary():
    now = int(time.time())
    with _lock:
        connects = sum(1 for e in recent_events if e[1] == "connected")
        disconnects = sum(1 for e in recent_events if e[1] == "disconnected")
        hist = list(client_count_history)
        sampled = hist[::max(1, int(60 / POLL_INTERVAL_SEC))]
        return {
            "ts": now,
            "connects_24h": connects,
            "disconnects_24h": disconnects,
            "history": sampled,
            "live_num_sta": len(latest_clients),
        }
