import re, time
from datetime import datetime

def parse_hostapd_status(text):
    data = {}
    for line in text.splitlines():
        if "=" in line:
            k, v = line.split("=", 1)
            data[k.strip()] = v.strip()
    for f in ["freq","channel","num_sta"]:
        if f in data:
            try: data[f] = int(data[f])
            except: pass
    return data

def parse_all_sta(text):
    clients, current_mac = {}, None
    for raw in text.splitlines():
        line = raw.strip()
        if not line: continue
        if re.match(r"^[0-9a-f]{2}(:[0-9a-f]{2}){5}$", line, re.I):
            current_mac = line.lower()
            clients[current_mac] = {}
            continue
        if current_mac and "=" in line:
            k, v = line.split("=", 1)
            v = v.strip()
            if v.isdigit():
                try: v = int(v)
                except: pass
            else:
                try:
                    if re.match(r"^-?\d+\.\d+$", v): v = float(v)
                except: pass
            clients[current_mac][k.strip()] = v
    for mac, d in clients.items():
        for rk in ("rx_rate","tx_rate"):
            if rk in d:
                try: d[rk+"_mbps"] = round(float(d[rk])/1000.0,1)
                except: pass
        if "signal" in d: 
            try: d["signal_dbm"] = int(d["signal"])
            except: pass
        elif "signal_avg" in d:
            try: d["signal_dbm"] = int(d["signal_avg"])
            except: pass
        if "connected_time" in d and isinstance(d["connected_time"], int):
            d["connected_h"] = round(d["connected_time"]/3600, 2)
    return clients

def scan_logs(paths, max_lines=5000):
    events, now = [], time.time()
    cutoff = now - 24*3600
    pat_connect = re.compile(r"AP-STA-CONNECTED\s+([0-9a-f:]{17})", re.I)
    pat_disconnect = re.compile(r"AP-STA-DISCONNECTED\s+([0-9a-f:]{17})", re.I)
    for p in paths:
        try:
            with open(p, "r", errors="ignore") as f:
                f.seek(0,2); size=f.tell()
                pos=max(0, size-200000); f.seek(pos)
                lines=f.read().splitlines()[-max_lines:]
        except Exception: continue
        for line in lines:
            ts=None
            m=re.match(r"^(\w{3}\s+\d{1,2}\s+\d{2}:\d{2}:\d{2})\s+", line)
            if m:
                try:
                    ts_dt=datetime.strptime(
                        m.group(1)+f" {datetime.now().year}",
                        "%b %d %H:%M:%S %Y")
                    ts=ts_dt.timestamp()
                except: ts=None
            if ts is None: ts=now
            if ts<cutoff: continue
            if (mc:=pat_connect.search(line)):
                events.append((ts,"connected",mc.group(1).lower()))
            elif (md:=pat_disconnect.search(line)):
                events.append((ts,"disconnected",md.group(1).lower()))
    return events
