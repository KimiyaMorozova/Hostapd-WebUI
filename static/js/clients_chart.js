const ctx = document.getElementById('clientsChart').getContext('2d');
const signalCtx = document.getElementById('signalChart').getContext('2d');
const bandwidthCtx = document.getElementById('bandwidthChart').getContext('2d');
let clientsChart, signalChart, bandwidthChart;
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
                        plugins: {
                            tooltip: { enabled: true },
                            zoom: { zoom: { wheel: { enabled: true }, pinch: { enabled: true }, mode: 'xy' } }
                        },
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

    // Signal Chart
    fetch('/api/signal_history')
        .then(r => r.json())
        .then(data => {
            const labels = data.map(p => {
                const d = new Date(p.time);
                const hours = d.getHours().toString().padStart(2, '0');
                const minutes = d.getMinutes().toString().padStart(2, '0');
                const seconds = d.getSeconds().toString().padStart(2, '0');
                return `${d.toLocaleDateString()} ${hours}:${minutes}:${seconds}`;
            });

            const signalData = data.map(p => Number(p.avg_signal) || 0);
            const ds = downsample(signalData, labels, 50);

            if (!signalChart) {
                signalChart = new Chart(signalCtx, {
                    type: 'line',
                    data: {
                        labels: ds.labels,
                        datasets: [{
                            label: 'Avg Signal (dBm)',
                            data: ds.data,
                            borderColor: 'rgba(255,99,132,1)',
                            backgroundColor: 'rgba(255,99,132,0.2)',
                            fill: true
                        }]
                    },
                    options: {
                        responsive: true,
                        animation: false,
                        plugins: {
                            tooltip: { enabled: true },
                            zoom: { zoom: { wheel: { enabled: true }, pinch: { enabled: true }, mode: 'xy' } }
                        },
                        scales: {
                            x: {
                                ticks: {
                                autoSkip: true,
                                maxTicksLimit: MAX_VISIBLE_TICKS,
                                }
                            },
                            y: { beginAtZero: false, min: -100, max: 0 }
                        },
                        elements: {
                            line: { tension: 0.3 }
                        }
                    }
                });
            } else {
                signalChart.data.labels = ds.labels;
                signalChart.data.datasets[0].data = ds.data;
                signalChart.update();
            }
        });

    // Bandwidth Chart
    fetch('/api/bandwidth_history')
        .then(r => r.json())
        .then(data => {
            const labels = data.map(p => {
                const d = new Date(p.time);
                const hours = d.getHours().toString().padStart(2, '0');
                const minutes = d.getMinutes().toString().padStart(2, '0');
                const seconds = d.getSeconds().toString().padStart(2, '0');
                return `${d.toLocaleDateString()} ${hours}:${minutes}:${seconds}`;
            });

            const txData = data.map(p => Number(p.tx_rate) || 0);
            const rxData = data.map(p => Number(p.rx_rate) || 0);
            const dsTx = downsample(txData, labels, 50);
            const dsRx = downsample(rxData, labels, 50);

            if (!bandwidthChart) {
                bandwidthChart = new Chart(bandwidthCtx, {
                    type: 'line',
                    data: {
                        labels: dsTx.labels,
                        datasets: [{
                            label: 'TX (packets/s)',
                            data: dsTx.data,
                            borderColor: 'rgba(54,162,235,1)',
                            backgroundColor: 'rgba(54,162,235,0.2)',
                            fill: false
                        }, {
                            label: 'RX (packets/s)',
                            data: dsRx.data,
                            borderColor: 'rgba(255,206,86,1)',
                            backgroundColor: 'rgba(255,206,86,0.2)',
                            fill: false
                        }]
                    },
                    options: {
                        responsive: true,
                        animation: false,
                        plugins: {
                            tooltip: { enabled: true },
                            zoom: { zoom: { wheel: { enabled: true }, pinch: { enabled: true }, mode: 'xy' } }
                        },
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
                            line: { tension: 0.3 }
                        }
                    }
                });
            } else {
                bandwidthChart.data.labels = dsTx.labels;
                bandwidthChart.data.datasets[0].data = dsTx.data;
                bandwidthChart.data.datasets[1].data = dsRx.data;
                bandwidthChart.update();
            }
        });
}

// Initial laden
updateChart();

// Alle 10 Sekunden updaten
setInterval(updateChart, 10000);
