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
        });
}

function updateDevices() {
    fetch('/api/devices')
        .then(response => response.json())
        .then(macs => {
            const tbody = document.getElementById('clients-body');
            tbody.innerHTML = ''; // Leere die Tabelle

            // Für jede MAC-Adresse die Details holen
            macs.forEach(mac => {
                fetch('/api/device/' + mac)
                    .then(response => response.json())
                    .then(device => {
                        if (device.mac) {  // Nur wenn Daten vorhanden
                            const row = document.createElement('tr');
                            row.innerHTML = `
                                <td>${device.mac}</td>
                                <td>${device.signal}</td>
                                <td>${device.tx_rate} / ${device.rx_rate}</td>
                                <td>${device.tx_packets} / ${device.rx_packets}</td>
                                <td>${device.tx_bytes} / ${device.rx_bytes}</td>
                                <td>${parseInt(device.connected_time) > 0 ? 'Yes' : 'No'}</td>
                                <td>${device.auth}</td>
                                <td>${device.inactive}</td>
                            `;
                            tbody.appendChild(row);
                        }
                    })
                    .catch(err => {
                        console.error("Fehler beim Laden der Geräte-Daten für", mac, err);
                    });
            });

            // Aktualisiere die Anzahl der verbundenen Clients
            document.getElementById('live-num').textContent = macs.length;
        })
        .catch(err => {
            console.error("Fehler beim Laden der Geräte-Liste:", err);
        });
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

// Initiales Laden
updateAPInfo();
updateDevices();
updateEvents();

// Optional: alle 5 Sekunden updaten
setInterval(updateAPInfo, 5000);
setInterval(updateDevices, 5000);
setInterval(updateEvents, 5000);  // Events alle 5 Sekunden updaten
