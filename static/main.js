let chart;
let pollInterval = 5000;
let iface = '';
let historyMinutes = 120;

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

// Fetch config from server (optional, or set via template)
async function fetchConfig() {
  // You can implement a /api/config endpoint if you want to set pollInterval, iface, historyMinutes dynamically
  // For now, set them statically or via data-attributes if needed
  document.getElementById('poll-interval').textContent = (pollInterval/1000).toString();
  document.getElementById('iface').textContent = iface;
  document.getElementById('history-minutes').textContent = historyMinutes;
}

fetchConfig();
fetchStatus();
setInterval(fetchStatus, pollInterval);
