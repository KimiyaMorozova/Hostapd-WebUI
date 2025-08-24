import threading
import time
import subprocess
from config import HOSTAPD_CLI, IFACE, LOG_PATHS, MAX_LOG_SCAN_LINES, POLL_INTERVAL_SEC
from state import lock, latest_status, latest_clients, client_count_history, recent_events, stop_event

bg = None

# Moved the required functions from utils.py to avoid circular imports
def run_cmd(cmd):
    try:
        return subprocess.check_output(cmd, stderr=subprocess.STDOUT, text=True).strip()
    except subprocess.CalledProcessError as e:
        return None

def parse_hostapd_status(text):
    # Parsing logic here
    return {}

def parse_all_sta(text):
    # Parsing logic here
    return {}

def scan_logs(paths, max_lines):
    # Scanning logic here
    return []

def poller():
    while not stop_event.is_set():
        status_text = run_cmd([HOSTAPD_CLI, '-i', IFACE, 'status'])
        status = parse_hostapd_status(status_text) if status_text else {}

        sta_text = run_cmd([HOSTAPD_CLI, '-i', IFACE, 'all_sta'])
        clients = parse_all_sta(sta_text) if sta_text else {}

        ev = scan_logs(LOG_PATHS, MAX_LOG_SCAN_LINES)

        with lock:
            latest_status.clear()
            latest_status.update(status)
            latest_clients.clear()
            latest_clients.update(clients)
            ts = int(time.time())
            client_count_history.append((ts, len(clients)))
            now = time.time()
            while recent_events and recent_events[0][0] < now - 24*3600:
                recent_events.popleft()
            for e in ev:
                recent_events.append(e)
        time.sleep(POLL_INTERVAL_SEC)

def start_poller():
    global bg
    if bg is None or not bg.is_alive():
        bg = threading.Thread(target=poller, daemon=True)
        bg.start()

def stop_poller():
    stop_event.set()
    if bg:
        bg.join(timeout=1)
