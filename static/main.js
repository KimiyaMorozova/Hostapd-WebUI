async function fetchClients() {
  try {
      let res = await fetch("/api/clients");
      let data = await res.json();
      let tbody = document.querySelector("#clients tbody");
      tbody.innerHTML = "";

      if (data.length === 0) {
          tbody.innerHTML = "<tr><td colspan='5'>Keine Clients verbunden</td></tr>";
          return;
      }

      data.forEach(c => {
          let row = `<tr>
              <td>${c.mac}</td>
              <td>${c.signal || "-"}</td>
              <td>${c.tx_bytes || 0}</td>
              <td>${c.rx_bytes || 0}</td>
              <td>${c.inactive || 0}</td>
          </tr>`;
          tbody.innerHTML += row;
      });
  } catch (err) {
      console.error("Fehler:", err);
  }
}

setInterval(fetchClients, 3000);
window.onload = fetchClients;
