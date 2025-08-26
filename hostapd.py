import re, time, subprocess, threading, atexit, logging, traceback
from datetime import datetime
from state import HOSTAPD_CLI, IFACE, LOG_PATHS, MAX_LOG_SCAN_LINES, POLL_INTERVAL_SEC
from state import latest_status, latest_clients, client_count_history, recent_events, lock, stop_event

logger = logging.getLogger("hostapd.poller")

def run_cmd(cmd, timeout=5):
    logger.debug("run_cmd: %s", cmd)
    try:
        out = subprocess.check_output(cmd, stderr=subprocess.STDOUT, timeout=timeout)
        result = out.decode(errors="ignore")
        logger.debug("run_cmd output len=%d", len(result))
        return result
    except subprocess.CalledProcessError as e:
        logger.error("run_cmd CalledProcessError: %s", e)
        try:
            return e.output.decode(errors="ignore")
        except:
            return ""
    except Exception as e:
        logger.exception("run_cmd exception")
        return ""


def parse_hostapd_status(text):
    try:
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
        logger.debug("parse_hostapd_status parsed %d keys", len(data))
        return data
    except Exception:
        logger.exception("parse_hostapd_status failed")
        return {}


def parse_all_sta(text):
    try:
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
                if v.isdigit():
                    try:
                        v = int(v)
                    except: pass
                else:
                    try:
                        if re.match(r"^-?\d+\.\d+$", v):
                            v = float(v)
                    except: pass
                clients[current_mac][k] = v
        # friendly aliases
        for mac, d in clients.items():
            for rate_key in ("rx_rate", "tx_rate"):
                if rate_key in d:
                    try:
                        kbps = float(d[rate_key])
                        d[rate_key + "_mbps"] = round(kbps / 1000.0, 1)
                    except: pass
            if 'signal' in d:
                try:
                    d['signal_dbm'] = int(d['signal'])
                except: pass
            elif 'signal_avg' in d:
                try:
                    d['signal_dbm'] = int(d['signal_avg'])
                except: pass
            if 'connected_time' in d and isinstance(d['connected_time'], int):
                d['connected_h'] = round(d['connected_time'] / 3600, 2)
        logger.debug("parse_all_sta parsed %d clients", len(clients))
        return clients
    except Exception:
        logger.exception("parse_all_sta failed")
        return {}


def scan_logs(paths, max_lines=5000):
    try:
        events = []
        now = time.time()
        cutoff = now - 24 * 3600
        pat_connect = re.compile(r"AP-STA-CONNECTED\s+([0-9a-f:]{17})", re.I)
        pat_disconnect = re.compile(r"AP-STA-DISCONNECTED\s+([0-9a-f:]{17})", re.I)
        for p in paths:
            try:
                with open(p, 'r', errors='ignore') as f:
                    f.seek(0, os.SEEK_END)
                    size = f.tell()
                    back = 200000
                    pos = max(0, size - back)
                    f.seek(pos)
                    lines = f.read().splitlines()[-max_lines:]
            except Exception:
                logger.debug("scan_logs: cannot open %s", p)
                continue
            for line in lines:
                ts = None
                m = re.match(r"^(\w{3}\s+\d{1,2}\s+\d{2}:\d{2}:\d{2})\s+", line)
                if m:
                    try:
                        ts_dt = datetime.strptime(m.group(1) + f" {datetime.now().year}", "%b %d %H:%M:%S %Y")
                        ts = ts_dt.timestamp()
                    except:
                        ts = None
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
        logger.debug("scan_logs found %d events", len(events))
        return events
    except Exception:
        logger.exception("scan_logs failed")
        return []


# ---------------------- Poller Thread ----------------------

def poller():
    logger.info("poller thread started for iface=%s", IFACE)
    while not stop_event.is_set():
        try:
            status_text = run_cmd([HOSTAPD_CLI, '-i', IFACE, 'status'])
            clients_text = run_cmd([HOSTAPD_CLI, '-i', IFACE, 'all_sta'])
            
            status = parse_hostapd_status(status_text) if status_text else {}
            clients = parse_all_sta(clients_text) if clients_text else {}
            ev = scan_logs(LOG_PATHS, MAX_LOG_SCAN_LINES)
            
            with lock:
                global latest_status, latest_clients
                latest_status = status
                latest_clients = clients
                # update history
                client_count_history.append((int(time.time()), len(clients)))
                # update events
                now = time.time()
                while recent_events and recent_events[0][0] < now - 24*3600:
                    recent_events.popleft()
                for e in ev:
                    recent_events.append(e)
            logger.debug("poller iteration: clients=%d events=%d", len(clients), len(ev))
        except Exception:
            logger.exception("poller iteration failed")
        time.sleep(POLL_INTERVAL_SEC)
    logger.info("poller thread stopping")

bg = threading.Thread(target=poller, daemon=True)
bg.start()

@atexit.register
def _cleanup():
    stop_event.set()
    try:
        bg.join(timeout=1)
    except Exception:
        logger.exception("cleanup join failed")

