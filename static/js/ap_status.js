function updateAPInfo() {
    fetch('/api/status')
        .then(response => response.json())
        .then(data => {
            const apInfoDiv = document.getElementById('ap-info');
            apInfoDiv.innerHTML = `
                Active: ${data.active}<br>
                Interface: ${data.interface}<br>
                SSID: ${data.ssid}<br>
                Channel: ${data.channel}<br>
                Frequency: ${data.frequency}
            `;
        })
        .catch(err => {
            console.error("Fehler beim Laden der AP-Daten:", err);
            const apInfoDiv = document.getElementById('ap-info');
            apInfoDiv.innerHTML = 'Error loading AP info';
        });
}

function updateDevices() {
    fetch('/api/devices')
        .then(response => response.json())
        .then(macs => {
            const tbody = document.getElementById('clients-body');
            const existingRows = Array.from(tbody.querySelectorAll('tr'));
            const existingMacs = existingRows.map(row => row.dataset.mac);

            // Neue MACs, die hinzugefügt werden müssen
            const newMacs = macs.filter(mac => !existingMacs.includes(mac));
            // Alte MACs, die entfernt werden müssen
            const oldMacs = existingMacs.filter(mac => !macs.includes(mac));

            // Entferne alte Zeilen
            oldMacs.forEach(mac => {
                const row = existingRows.find(r => r.dataset.mac === mac);
                if (row) tbody.removeChild(row);
            });

            // Aktualisiere bestehende und füge neue hinzu
            macs.forEach(mac => {
                const existingRow = existingRows.find(r => r.dataset.mac === mac);
                if (existingRow) {
                    // Aktualisiere die Zeile
                    updateDeviceRow(existingRow, mac);
                } else {
                    // Neue Zeile hinzufügen
                    const row = document.createElement('tr');
                    row.dataset.mac = mac;
                    tbody.appendChild(row);
                    updateDeviceRow(row, mac);
                }
            });

            // Aktualisiere die Anzahl der verbundenen Clients
            document.getElementById('live-num').textContent = macs.length;
        })
        .catch(err => {
            console.error("Fehler beim Laden der Geräte-Liste:", err);
        });
}

const prevStats = new Map(); // mac -> {tx_packets, rx_packets, time}

function updateDeviceRow(row, mac) {
    fetch('/api/device/' + mac)
        .then(response => response.json())
        .then(device => {
            if (device.mac) {
                const now = Date.now();
                const prev = prevStats.get(mac) || { tx_packets: 0, rx_packets: 0, time: now };
                const timeDiff = (now - prev.time) / 1000; // Sekunden

                const txRate = timeDiff > 0 ? ((parseInt(device.tx_packets) - prev.tx_packets) / timeDiff).toFixed(1) : 0;
                const rxRate = timeDiff > 0 ? ((parseInt(device.rx_packets) - prev.rx_packets) / timeDiff).toFixed(1) : 0;

                prevStats.set(mac, { tx_packets: parseInt(device.tx_packets), rx_packets: parseInt(device.rx_packets), time: now });

                row.innerHTML = `
                    <td>${device.mac}</td>
                    <td class="${getSignalClass(device.signal)}">${device.signal}</td>
                    <td>${txRate} / ${rxRate}</td>
                    <td>${device.tx_packets} / ${device.rx_packets}</td>
                    <td>${formatTime(parseInt(device.connected_time) || 0)}</td>
                    <td>${formatInactive(parseInt(device.inactive) || 0)}</td>
                `;
            }
        })
        .catch(err => {
            console.error("Fehler beim Laden der Geräte-Daten für", mac, err);
        });
}

function getSignalClass(signal) {
    const sig = parseInt(signal);
    if (isNaN(sig)) return '';
    if (sig > -60) return 'signal-good';
    if (sig > -75) return 'signal-medium';
    return 'signal-bad';
}

function formatTime(seconds) {
    const hrs = Math.floor(seconds / 3600);
    const mins = Math.floor((seconds % 3600) / 60);
    const secs = seconds % 60;
    if (hrs > 0) {
        return `${hrs}h ${mins}min ${secs}s`;
    } else if (mins > 0) {
        return `${mins}min ${secs}s`;
    } else {
        return `${secs}s`;
    }
}

function formatInactive(ms) {
    const totalSeconds = Math.floor(ms / 1000);
    const millis = ms % 1000;
    if (totalSeconds > 0) {
        return `${totalSeconds}s ${millis}ms`;
    } else {
        return `${millis}ms`;
    }
}

function updateEvents() {
    fetch('/api/events')
        .then(response => response.json())
        .then(data => {
            document.getElementById('ev-conn').textContent = data.connected;
            document.getElementById('ev-disc').textContent = data.disconnected;
        })
        .catch(err => {
            console.error("Fehler beim Laden der Events:", err);
        });
}

function controlHostapd(action) {
    fetch('/api/hostapd/' + action, { method: 'POST' })
        .then(response => response.json())
        .then(data => {
            document.getElementById('control-status').textContent = data.status || data.error;
        })
        .catch(err => {
            console.error("Fehler bei Hostapd Control:", err);
            document.getElementById('control-status').textContent = "Error: " + err.message;
        });
}

// Initiales Laden
updateAPInfo();
updateDevices();
updateEvents();

// Optional: alle 5 Sekunden updaten
setInterval(updateAPInfo, 5000);
setInterval(updateDevices, 1000);
setInterval(updateEvents, 5000);  // Events alle 5 Sekunden updaten
