#!/usr/bin/env python3
"""
Hostapd Dashboard – single-file Flask app

Features
- Reads live station data via `hostapd_cli -i <iface> all_sta`
- Gets AP status via `hostapd_cli -i <iface> status`
- Parses recent hostapd/syslog lines for connect/disconnect events
- Simple dashboard with live-updating tables & charts (no DB needed)
- Works on a "dumb AP" (no DHCP/DNS on the box)

Dependencies
- Python 3.9+
- Flask (pip install flask)
- hostapd_cli available and the Flask process has permission to read the control socket

Run
  export HOSTAPD_IFACE=wlan0   # or your interface
  export HOSTAPD_LOG=/var/log/hostapd.log  # optional; comma-separated list supported
  python3 hostapd_dashboard.py
Then open http://0.0.0.0:8080

Security
- Intended for LAN/admin use. Bind to 127.0.0.1 and reverse-proxy if exposed. No auth included.
"""
import os
import re
import json
import time
import queue
import math
import shlex
import atexit
import signal
import threading
import subprocess
from datetime import datetime, timedelta
from collections import defaultdict, deque

from flask import Flask, jsonify, request, Response, render_template_string

# ---------------------- Configuration ----------------------
HOST = os.getenv("DASHBOARD_HOST", "0.0.0.0")
PORT = int(os.getenv("DASHBOARD_PORT", 8080))
IFACE = os.getenv("HOSTAPD_IFACE", "wlan0")
HOSTAPD_CLI = os.getenv("HOSTAPD_CLI", "/usr/sbin/hostapd_cli")
LOG_PATHS = [p for p in os.getenv("HOSTAPD_LOG", "/var/log/hostapd.log,/var/log/syslog").split(";") for p in p.split(",")]
LOG_PATHS = [p.strip() for p in LOG_PATHS if p.strip()]
MAX_LOG_SCAN_LINES = int(os.getenv("MAX_LOG_LINES", 5000))
POLL_INTERVAL_SEC = float(os.getenv("POLL_INTERVAL", 5))
HISTORY_MINUTES = int(os.getenv("HISTORY_MINUTES", 120))  # for client-count chart

# ---------------------- State ----------------------
lock = threading.Lock()
latest_status = {}
latest_clients = {}
# history of (timestamp, client_count)
client_count_history = deque(maxlen=HISTORY_MINUTES * max(1, int(60 / POLL_INTERVAL_SEC)))
# simple event counters in last 24h
recent_events = deque(maxlen=20000)  # list of (ts, type, mac)

stop_event = threading.Event()

# ---------------------- Helpers ----------------------

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

# ---------------------- Web ----------------------
app = Flask(__name__)


@app.get("/api/clients")
def api_clients():
    with lock:
        data = {
            'ts': int(time.time()),
            'clients': latest_clients,
        }
    return jsonify(data)


@app.get("/api/status")
def api_status():
    with lock:
        status = latest_status.copy()
        # enrich with live count
        status['live_num_sta'] = len(latest_clients)
    return jsonify(status)


@app.get("/api/summary")
def api_summary():
    now = int(time.time())
    with lock:
        # events in last 24h
        connects = sum(1 for e in recent_events if e[1] == 'connected')
        disconnects = sum(1 for e in recent_events if e[1] == 'disconnected')
        # history lists
        hist = list(client_count_history)
        # sample every ~minute for chart simplicity
        sampled = hist[::max(1, int(60 / POLL_INTERVAL_SEC))]
        summary = {
            'ts': now,
            'connects_24h': connects,
            'disconnects_24h': disconnects,
            'history': sampled,
            'live_num_sta': len(latest_clients),
        }
    return jsonify(summary)


INDEX_HTML = """
<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Hostapd Dashboard</title>
  <script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
  <link rel="preconnect" href="https://fonts.googleapis.com">
  <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
  <link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;600;700&display=swap" rel="stylesheet">
  <style>
    :root { --bg: #0b1020; --card: #121729; --text: #eef2ff; --muted:#a5b4fc; --ok:#34d399; --warn:#fbbf24; --bad:#f87171; }
    * { box-sizing: border-box; }
    body { margin:0; font-family: Inter, system-ui, sans-serif; background: linear-gradient(180deg,#0b1020,#0d1326 40%,#0b1020); color: var(--text); }
    .wrap { max-width: 1100px; margin: 32px auto; padding: 0 16px; }
    .grid { display:grid; gap:16px; }
    .grid.cards { grid-template-columns: repeat(auto-fit,minmax(220px,1fr)); }
    .card { background: var(--card); border:1px solid #1f2540; border-radius: 16px; padding: 16px; box-shadow: 0 10px 30px rgba(0,0,0,0.25); }
    .title { font-weight:700; font-size: 20px; }
    .muted { color: var(--muted); font-size: 12px; }
    table { width:100%; border-collapse: collapse; }
    th, td { padding: 10px; border-bottom: 1px solid #1f2540; font-size: 14px; text-align: left; }
    th { position: sticky; top: 0; background: #151b33; }
    .tag { display:inline-block; padding:2px 8px; border-radius:999px; font-size:12px; background:#1f2540; }
    .good { color: var(--ok); }
    .warn { color: var(--warn); }
    .bad { color: var(--bad); }
    .footer { opacity:.7; font-size:12px; margin-top:24px; }
    .hint { font-size: 12px; color: var(--muted); }
  </style>
</head>
<body>
  <div class="wrap">
    <div class="grid cards">
      <div class="card">
        <div class="title">Access Point</div>
        <div id="ap-info" class="muted">Loading…</div>
      </div>
      <div class="card">
        <div class="title">Connected clients</div>
        <div style="font-size:40px;font-weight:700" id="live-num">0</div>
        <div class="hint">live</div>
      </div>
      <div class="card">
        <div class="title">24h Events</div>
        <div><span class="good">⬆ <span id="ev-conn">0</span></span> &nbsp; <span class="bad">⬇ <span id="ev-disc">0</span></span></div>
        <div class="hint">connect / disconnect</div>
      </div>
    </div>

    <div class="card" style="margin-top:16px">
      <div class="title" style="margin-bottom:8px">Client Count (last ~{{history_minutes}} min)</div>
      <canvas id="clientsChart" height="90"></canvas>
    </div>

    <div class="card" style="margin-top:16px">
      <div class="title" style="margin-bottom:8px">Connected Devices</div>
      <div class="hint">No DHCP/DNS on AP: devices are shown by MAC. Rates are negotiated link rates, not actual throughput.</div>
      <div style="max-height: 420px; overflow: auto; margin-top: 8px">
      <table>
        <thead>
          <tr>
            <th>MAC</th>
            <th>Signal (dBm)</th>
            <th>TX / RX (Mbps)</th>
            <th>TX / RX (pkts)</th>
            <th>Bytes TX / RX</th>
            <th>Connected</th>
            <th>Auth</th>
            <th>Inactive (s)</th>
          </tr>
        </thead>
        <tbody id="clients-body">
        </tbody>
      </table>
      </div>
    </div>

    <div class="footer muted">Powered by hostapd_cli • Refresh every {{poll}}s • Interface: <code>{{iface}}</code></div>
  </div>
<script>
let chart;
function classifySignal(dbm){
  if (dbm === undefined || dbm === null) return '';
  if (dbm >= -60) return 'good';
  if (dbm >= -75) return 'warn';
  return 'bad';
}
function fmtBytes(n){
  if(n===undefined||n===null) return '';
  const units=['B','KB','MB','GB','TB'];
  let i=0; let x = Number(n);
  while(x>=1024 && i<units.length-1){x/=1024;i++;}
  return x.toFixed(1)+' '+units[i];
}
async function fetchStatus(){
  const [status, summary, clients] = await Promise.all([
    fetch('/api/status').then(r=>r.json()),
    fetch('/api/summary').then(r=>r.json()),
    fetch('/api/clients').then(r=>r.json())
  ]);
  // AP info
  const ap = status;
  const parts = [];
  if(ap.ssid) parts.push(`<b>${ap.ssid}</b>`);
  if(ap.bssid) parts.push(`BSSID ${ap.bssid}`);
  if(ap.channel) parts.push(`Ch ${ap.channel}`);
  if(ap.freq) parts.push(`${ap.freq} MHz`);
  if(ap.hw_mode) parts.push(ap.hw_mode);
  if(ap.ieee80211n=='1') parts.push('11n');
  if(ap.ieee80211ac=='1') parts.push('11ac');
  if(ap.ieee80211ax=='1') parts.push('11ax');
  document.getElementById('ap-info').innerHTML = parts.join(' • ') || '—';

  document.getElementById('live-num').textContent = clients && clients.clients ? Object.keys(clients.clients).length : 0;
  document.getElementById('ev-conn').textContent = summary.connects_24h || 0;
  document.getElementById('ev-disc').textContent = summary.disconnects_24h || 0;

  // Clients table
  const tbody = document.getElementById('clients-body');
  tbody.innerHTML = '';
  if (clients && clients.clients){
    const entries = Object.entries(clients.clients).sort();
    for (const [mac, d] of entries){
      const sig = d.signal_dbm ?? d.signal ?? d.signal_avg;
      const tr = document.createElement('tr');
      tr.innerHTML = `
        <td><code>${mac}</code></td>
        <td class="${classifySignal(sig)}">${sig ?? ''}</td>
        <td>${(d.tx_rate_mbps ?? '')} / ${(d.rx_rate_mbps ?? '')}</td>
        <td>${(d.tx_packets ?? '')} / ${(d.rx_packets ?? '')}</td>
        <td>${fmtBytes(d.tx_bytes)} / ${fmtBytes(d.rx_bytes)}</td>
        <td>${d.connected_time ? (d.connected_time+'s') : ''}</td>
        <td>${d.authorized ?? ''}</td>
        <td>${d.inactive ?? ''}</td>
      `;
      tbody.appendChild(tr);
    }
  }

  // Chart
  const hist = summary.history || [];
  const labels = hist.map(([ts,_])=> new Date(ts*1000).toLocaleTimeString());
  const data = hist.map(([_,c])=> c);
  if(!chart){
    const ctx = document.getElementById('clientsChart').getContext('2d');
    chart = new Chart(ctx, {
      type: 'line',
      data: { labels, datasets: [{ label: 'Clients', data }] },
      options: { responsive: true, scales: { y: { beginAtZero: true, ticks: { precision:0 } } } }
    });
  } else {
    chart.data.labels = labels; chart.data.datasets[0].data = data; chart.update();
  }
}
fetchStatus();
setInterval(fetchStatus, {{interval}});
</script>
</body>
</html>
"""


@app.get("/")
def index():
    return render_template_string(INDEX_HTML, iface=IFACE, poll=POLL_INTERVAL_SEC, interval=int(POLL_INTERVAL_SEC*1000), history_minutes=HISTORY_MINUTES)


# ---------------------- Entrypoint ----------------------
if __name__ == "__main__":
    # allow Ctrl+C
    signal.signal(signal.SIGINT, signal.SIG_DFL)
    app.run(host=HOST, port=PORT, debug=False)