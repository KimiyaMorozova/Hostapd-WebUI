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
        .then(devices => {
            const tbody = document.getElementById('clients-body');
            tbody.innerHTML = ''; // Leere die Tabelle

            devices.forEach(device => {
                const row = document.createElement('tr');
                row.innerHTML = `
                    <td>${device.mac}</td>
                    <td>${device.signal}</td>
                    <td>${device.tx_rate} / ${device.rx_rate}</td>
                    <td>${device.tx_packets} / ${device.rx_packets}</td>
                    <td>${device.tx_bytes} / ${device.rx_bytes}</td>
                    <td>${device.connected_time}</td>
                    <td>${device.auth}</td>
                    <td>${device.inactive}</td>
                `;
                tbody.appendChild(row);
            });

            // Aktualisiere die Anzahl der verbundenen Clients
            document.getElementById('live-num').textContent = devices.length;
        })
        .catch(err => {
            console.error("Fehler beim Laden der Geräte-Daten:", err);
        });
}

// Initiales Laden
updateAPInfo();
updateDevices();

// Optional: alle 5 Sekunden updaten
setInterval(updateAPInfo, 5000);
setInterval(updateDevices, 5000);
