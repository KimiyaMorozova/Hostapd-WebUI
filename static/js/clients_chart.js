const ctx = document.getElementById('clientsChart').getContext('2d');
let clientsChart;
const MAX_VISIBLE_TICKS = 10; // inkl. erstes + letztes Label

// Gleichmäßiges Downsampling: immer erstes + letztes + einige mittlere
function downsample(data, labels, maxPoints = 50) {
    const total = data.length;
    if (total <= maxPoints) return { data, labels };

    const step = (total - 1) / (maxPoints - 1);
    const newData = [];
    const newLabels = [];

    for (let i = 0; i < maxPoints; i++) {
        const idx = Math.round(i * step);
        newData.push(data[idx]);
        newLabels.push(labels[idx]);
    }

    return { data: newData, labels: newLabels };
}

// Chart aktualisieren
function updateChart() {
    fetch('/api/clients')
        .then(r => r.json())
        .then(data => {
            // Labels: Datum + Uhrzeit HH:MM:SS
            const labels = data.map(p => {
                const d = new Date(p.time);
                const hours = d.getHours().toString().padStart(2, '0');
                const minutes = d.getMinutes().toString().padStart(2, '0');
                const seconds = d.getSeconds().toString().padStart(2, '0');
                return `${d.toLocaleDateString()} ${hours}:${minutes}:${seconds}`;
            });

            const clientsData = data.map(p => Number(p.clients) || 0);
            const ds = downsample(clientsData, labels, 50);

            if (!clientsChart) {
                clientsChart = new Chart(ctx, {
                    type: 'line',
                    data: {
                        labels: ds.labels,
                        datasets: [{
                            label: 'Clients',
                            data: ds.data,
                            borderColor: 'rgba(75,192,192,1)',
                            backgroundColor: 'rgba(75,192,192,0.2)',
                            fill: true
                        }]
                    },
                    options: {
                        responsive: true,
                        animation: false,
                        scales: {
                            x: {
                                ticks: {
                                autoSkip: true,
                                maxTicksLimit: MAX_VISIBLE_TICKS,
                                }
                            },
                            y: { beginAtZero: true }
                        },
                        elements: {
                            line: { tension: 0.3 } // glatte Linie
                        }
                    }
                });
            } else {
                clientsChart.data.labels = ds.labels;
                clientsChart.data.datasets[0].data = ds.data;
                clientsChart.update();
            }
        });
}

// Initial laden
updateChart();

// Alle 10 Sekunden updaten
setInterval(updateChart, 10000);
