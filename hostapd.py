import re, time, subprocess, threading, atexit
from datetime import datetime
from state import HOSTAPD_CLI, IFACE, LOG_PATHS, MAX_LOG_SCAN_LINES, POLL_INTERVAL_SEC
from state import latest_status, latest_clients, client_count_history, recent_events, lock, stop_event

def run_cmd(cmd, timeout=5):
    try:
        out = subprocess.check_output(cmd, stderr=subprocess.STDOUT, timeout=timeout)
        return out.decode(errors="ignore")
    except Exception:
        return ""

def parse_hostapd_status(text):
    data = {}
    for line in text.splitlines():
        if "=" in line:
            k, v = line.split("=", 1)
            data[k.strip()] = v.strip()
    for key in ("freq","channel","num_sta"):
        if key in data:
            try: data[key] = int(data[key])
            except: pass
    return data

def parse_all_sta(text):
    clients = {}
    current_mac = None
    for raw in text.splitlines():
        line = raw.strip()
        if not line: continue
        if re.match(r"^[0-9a-f]{2}(:[0-9a-f]{2}){5}$", line, re.I):
            current_mac = line.lower()
            clients[current_mac] = {}
            continue
        if current_mac and "=" in line:
            k,v = line.split("=",1)
            v=v.strip()
            if v.isdigit(): v=int(v)
            else:
                try: v=float(v)
                except: pass
            clients[current_mac][k.strip()] = v
    for mac,d in clients.items():
        for rate_key in ("rx_rate","tx_rate"):
            if rate_key in d:
                try: d[rate_key+"_mbps"]=round(float(d[rate_key])/1000,1)
                except: pass
        if "signal" in d: d["signal_dbm"]=int(d["signal"])
        elif "signal_avg" in d: d["signal_dbm"]=int(d["signal_avg"])
        if "connected_time" in d and isinstance(d["connected_time"],int):
            d["connected_h"]=round(d["connected_time"]/3600,2)
    return clients

def scan_logs(paths, max_lines=5000):
    events=[]; now=time.time(); cutoff=now-24*3600
    pat_c=re.compile(r"AP-STA-CONNECTED\s+([0-9a-f:]{17})",re.I)
    pat_d=re.compile(r"AP-STA-DISCONNECTED\s+([0-9a-f:]{17})",re.I)
    for p in paths:
        try:
            with open(p,"r",errors="ignore") as f:
                f.seek(0,2); size=f.tell(); pos=max(0,size-200000)
                f.seek(pos); lines=f.read().splitlines()[-max_lines:]
        except: continue
        for line in lines:
            ts=now
            m=re.match(r"^(\w{3}\s+\d{1,2}\s+\d{2}:\d{2}:\d{2})\s+",line)
            if m:
                try: ts=datetime.strptime(m.group(1)+f" {datetime.now().year}","%b %d %H:%M:%S %Y").timestamp()
                except: pass
            if ts<cutoff: continue
            mc=pat_c.search(line); md=pat_d.search(line)
            if mc: events.append((ts,"connected",mc.group(1).lower()))
            if md: events.append((ts,"disconnected",md.group(1).lower()))
    return events

def poller():
    while not stop_event.is_set():
        status=parse_hostapd_status(run_cmd([HOSTAPD_CLI,"-i",IFACE,"status"]))
        clients=parse_all_sta(run_cmd([HOSTAPD_CLI,"-i",IFACE,"all_sta"]))
        ev=scan_logs(LOG_PATHS,MAX_LOG_SCAN_LINES)
        with lock:
            global latest_status, latest_clients
            latest_status=status; latest_clients=clients
            ts=int(time.time())
            client_count_history.append((ts,len(clients)))
            now=time.time()
            while recent_events and recent_events[0][0]<now-24*3600:
                recent_events.popleft()
            for e in ev: recent_events.append(e)
        time.sleep(POLL_INTERVAL_SEC)

bg=threading.Thread(target=poller,daemon=True); bg.start()

@atexit.register
def _cleanup():
    stop_event.set()
    try: bg.join(timeout=1)
    except: pass
