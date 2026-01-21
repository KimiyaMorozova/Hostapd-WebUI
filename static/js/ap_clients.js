function updateAPInfo() {
    fetch('/api/devices')
        .then(response => response.json())
        .then(devices => {
            const apInfoDiv = document.getElementById('live-num');
            apInfoDiv.innerHTML = devices.length;
        })
        .catch(err => {
            console.error("Fehler beim Laden der AP-Daten:", err);
        });
}

// Initiales Laden
updateAPInfo();

// Optional: alle 5 Sekunden updaten
setInterval(updateAPInfo, 5000);
