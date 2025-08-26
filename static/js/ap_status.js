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
                Frequency: ${data.freq}
            `;
        })
        .catch(err => {
            console.error("Fehler beim Laden der AP-Daten:", err);
        });
}

// Initiales Laden
updateAPInfo();

// Optional: alle 5 Sekunden updaten
setInterval(updateAPInfo, 5000);
