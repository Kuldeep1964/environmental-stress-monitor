let envChart;
let stressGauge;

function initCharts() {

    const chartEl = document.getElementById("envChart");
    const gaugeEl = document.getElementById("stressGauge");

    if (!chartEl || !gaugeEl) return; // Prevent crash on other pages

    envChart = new Chart(chartEl.getContext("2d"), {
        type: "line",
        data: {
            labels: [],
            datasets: [
                { label: "Temperature", data: [], borderColor: "orange", tension: 0.4 },
                { label: "AQI", data: [], borderColor: "cyan", tension: 0.4 }
            ]
        }
    });

    stressGauge = new Chart(gaugeEl.getContext("2d"), {
        type: "doughnut",
        data: {
            datasets: [{
                data: [0, 100],
                backgroundColor: ["green", "#1f2937"],
                borderWidth: 0
            }]
        },
        options: {
            cutout: "80%",
            rotation: -90,
            circumference: 180,
            plugins: { legend: { display: false } }
        }
    });
}

function updateDashboard() {

    if (!document.getElementById("temp")) return;

    fetch("/data")
        .then(res => res.json())
        .then(data => {

            document.getElementById("temp").innerText = data.temperature + "°C";
            document.getElementById("hum").innerText = data.humidity + "%";
            document.getElementById("air").innerText = data.air;
            document.getElementById("people").innerText = data.people;
            document.getElementById("stressText").innerText = data.stress;
            document.getElementById("suggestion").innerText = data.suggestion;
            document.getElementById("lastUpdate").innerText = "Last Update: " + data.time;

            let value = data.stress === "LOW" ? 30 :
                        data.stress === "MEDIUM" ? 60 : 90;

            let color = data.stress === "LOW" ? "green" :
                        data.stress === "MEDIUM" ? "orange" : "red";

            if (stressGauge) {
                stressGauge.data.datasets[0].data = [value, 100 - value];
                stressGauge.data.datasets[0].backgroundColor = [color, "#1f2937"];
                stressGauge.update();
            }
        });

   fetch("/history")   // IMPORTANT: use correct API route
        .then(res => res.json())
        .then(history => {

            if (!history || history.length === 0) return;

            // Take only recent 10
            const recentLogs = history.slice(0, 10);

            // Update Chart
            if (envChart) {
                envChart.data.labels = recentLogs.map(h => h.time).reverse();
                envChart.data.datasets[0].data = recentLogs.map(h => h.temperature).reverse();
                envChart.data.datasets[1].data = recentLogs.map(h => h.air).reverse();
                envChart.update();
            }

            // Update Table
            const table = document.getElementById("historyTable");
            if (!table) return;

            table.innerHTML = "";

            recentLogs.forEach(row => {
                table.innerHTML += `
                    <tr class="border-b border-white/10 hover:bg-white/5 transition">
                        <td class="py-2">${row.time}</td>
                        <td>${row.temperature}</td>
                        <td>${row.humidity}</td>
                        <td>${row.air}</td>
                        <td>${row.people}</td>
                        <td class="font-semibold ${
                            row.stress === "HIGH" ? "text-red-400" :
                            row.stress === "MEDIUM" ? "text-orange-400" :
                            "text-green-400"
                        }">
                            ${row.stress}
                        </td>
                    </tr>`;
            });
        });
}

fetch("/api/weather")
.then(res => res.json())
.then(weather => {

    if (!weather) return;

    document.getElementById("weatherBox").innerHTML = `
        <div>🌡 Temperature: ${weather.outdoor_temp}°C || 💧 Humidity: ${weather.outdoor_humidity}% || 🌬 Wind Speed: ${weather.wind_speed} m/s || ☁ Condition: ${weather.weather}</div>
       
    `;
});

initCharts();
updateDashboard();
setInterval(updateDashboard, 4000);