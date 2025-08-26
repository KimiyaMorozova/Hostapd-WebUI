import re, time, subprocess, threading, atexit
from datetime import datetime
from state import HOSTAPD_CLI, IFACE, LOG_PATHS, MAX_LOG_SCAN_LINES, POLL_INTERVAL_SEC
from state import latest_status, latest_clients, client_count_history, recent_events, lock, stop_event

def run_cmd(cmd, timeout=5):
    try:
        out = subprocess.check_output(cmd, stderr=subprocess.STDOUT, timeout=timeout)
        return out.decode(errors="ignore")
    except subprocess.CalledProcessError as e:
        return e.output.decode(errors="ignore")
    except Exception as e:
        return ""


def parse_hostapd_status(text):
    data = {}
    for line in text.splitlines():
        if "=" in line:
            k, v = line.split("=", 1)
            data[k.strip()] = v.strip()
    # Normalize a few fields
    if 'freq' in data:
        try:
            data['freq'] = int(data['freq'])
        except: pass
    if 'channel' in data:
        try:
            data['channel'] = int(data['channel'])
        except: pass
    if 'num_sta' in data:
        try:
            data['num_sta'] = int(data['num_sta'])
        except: pass
    return data


def parse_all_sta(text):
    """Parse `hostapd_cli all_sta` output into dict keyed by MAC.
    Supports varying field presence; converts numbers when sensible.
    """
    clients = {}
    current_mac = None
    for raw in text.splitlines():
        line = raw.strip()
        if not line:
            continue
        if re.match(r"^[0-9a-f]{2}(:[0-9a-f]{2}){5}$", line, re.I):
            current_mac = line.lower()
            clients[current_mac] = {}
            continue
        if current_mac is None:
            continue
        if '=' in line:
            k, v = line.split('=', 1)
            k = k.strip()
            v = v.strip()
            # try cast
            if v.isdigit():
                try:
                    v = int(v)
                except: pass
            else:
                # numeric floats
                try:
                    if re.match(r"^-?\d+\.\d+$", v):
                        v = float(v)
                except: pass
            clients[current_mac][k] = v
    # friendly aliases
    for mac, d in clients.items():
        # negotiated rates are in kbps often (rx_rate/tx_rate). Convert to Mbps if numeric
        for rate_key in ("rx_rate", "tx_rate"):
            if rate_key in d:
                try:
                    kbps = float(d[rate_key])
                    d[rate_key + "_mbps"] = round(kbps / 1000.0, 1)
                except: pass
        # signal might be under 'signal' or 'signal_avg'
        if 'signal' in d:
            try:
                d['signal_dbm'] = int(d['signal'])
            except: pass
        elif 'signal_avg' in d:
            try:
                d['signal_dbm'] = int(d['signal_avg'])
            except: pass
        # connected_time is seconds; compute human readable
        if 'connected_time' in d and isinstance(d['connected_time'], int):
            d['connected_h'] = round(d['connected_time'] / 3600, 2)
    return clients


def scan_logs(paths, max_lines=5000):
    events = []
    now = time.time()
    cutoff = now - 24 * 3600
    pat_connect = re.compile(r"AP-STA-CONNECTED\s+([0-9a-f:]{17})", re.I)
    pat_disconnect = re.compile(r"AP-STA-DISCONNECTED\s+([0-9a-f:]{17})", re.I)
    for p in paths:
        try:
            with open(p, 'r', errors='ignore') as f:
                # Read last N lines cheaply
                f.seek(0, os.SEEK_END)
                size = f.tell()
                # rough back-seek window
                back = 200000
                pos = max(0, size - back)
                f.seek(pos)
                lines = f.read().splitlines()[-max_lines:]
        except Exception:
            continue
        for line in lines:
            ts = None
            # Try to parse syslog-like timestamp (Mmm dd hh:mm:ss)
            m = re.match(r"^(\w{3}\s+\d{1,2}\s+\d{2}:\d{2}:\d{2})\s+", line)
            if m:
                try:
                    # no year; assume current year
                    ts_dt = datetime.strptime(m.group(1) + f" {datetime.now().year}", "%b %d %H:%M:%S %Y")
                    ts = ts_dt.timestamp()
                except:
                    ts = None
            # Fallback to now
            if ts is None:
                ts = now
            if ts < cutoff:
                continue
            mc = pat_connect.search(line)
            if mc:
                events.append((ts, 'connected', mc.group(1).lower()))
                continue
            md = pat_disconnect.search(line)
            if md:
                events.append((ts, 'disconnected', md.group(1).lower()))
                continue
    return events


# ---------------------- Poller Thread ----------------------

def poller():
    while not stop_event.is_set():
        # hostapd status
        status_text = run_cmd([HOSTAPD_CLI, '-i', IFACE, 'status'])
        status = parse_hostapd_status(status_text) if status_text else {}

        # clients
        sta_text = run_cmd([HOSTAPD_CLI, '-i', IFACE, 'all_sta'])
        clients = parse_all_sta(sta_text) if sta_text else {}

        # logs (recent)
        ev = scan_logs(LOG_PATHS, MAX_LOG_SCAN_LINES)

        with lock:
            global latest_status, latest_clients
            latest_status = status
            latest_clients = clients
            # update client count history
            ts = int(time.time())
            client_count_history.append((ts, len(clients)))
            # update recent events
            # keep only last 24h window
            now = time.time()
            while recent_events and recent_events[0][0] < now - 24*3600:
                recent_events.popleft()
            for e in ev:
                recent_events.append(e)
        time.sleep(POLL_INTERVAL_SEC)


bg = threading.Thread(target=poller, daemon=True)
bg.start()

@atexit.register
def _cleanup():
    stop_event.set()
    try:
        bg.join(timeout=1)
    except Exception:
        pass

