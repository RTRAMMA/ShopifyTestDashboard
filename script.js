fetch("./daily_summary.csv")
  .then(r => r.text())
  .then(csv => setupDashboard(parseCSV(csv)));

function parseCSV(csv) {
  const rows = csv.trim().split("\n");
  rows.shift();
  return rows.map(r => {
    const v = r.split(",");
    return {
      date: v[0],
      revenue: parseFloat(v[1]),
      refunds: parseFloat(v[2]),
      net: parseFloat(v[3]),
      orders: parseInt(v[4])
    };
  });
}

function setupDashboard(data) {
  drawCharts(data);
  updateLastUpdatedStatus(data);

  const adInput = document.getElementById("adSpendInput");
  function recalc() {
    updateSummary(
      sum(data, "revenue"),
      sum(data, "refunds"),
      parseFloat(adInput.value) || 0
    );
  }
  recalc();
  adInput.addEventListener("input", recalc);
}

function updateSummary(revenue, refunds, adSpend) {
  const net = revenue - refunds - adSpend;
  const roas = adSpend > 0 ? revenue / adSpend : null;

  document.getElementById("totalRevenue").innerText = money(revenue);
  document.getElementById("totalRefunds").innerText = money(refunds);
  document.getElementById("netProfit").innerText = money(net);

  const roasEl = document.getElementById("roas");
  const statusEl = document.getElementById("status");

  if (!roas) {
    roasEl.innerText = "—";
    statusEl.innerText = "";
    return;
  }

  roasEl.innerText = roas.toFixed(2);
  statusEl.className = "";

  if (roas < 1) {
    statusEl.innerText = "RED";
    statusEl.classList.add("status-red");
  } else if (roas < 3) {
    statusEl.innerText = "YELLOW";
    statusEl.classList.add("status-yellow");
  } else {
    statusEl.innerText = "GREEN";
    statusEl.classList.add("status-green");
  }
}

function updateLastUpdatedStatus(data) {
  const badge = document.getElementById("updateBadge");
  const lastDate = new Date(data[data.length - 1].date);
  const today = new Date();

  lastDate.setHours(0,0,0,0);
  today.setHours(0,0,0,0);

  const diff = Math.round((today - lastDate) / 86400000);

  if (diff === 0) {
    badge.textContent = `✅ Up to date (last date: ${data[data.length - 1].date})`;
    badge.className = "badge bg-success";
  } else if (diff === 1) {
    badge.textContent = `🟡 Data from yesterday (${data[data.length - 1].date})`;
    badge.className = "badge bg-warning text-dark";
  } else {
    badge.textContent = `🔴 Data stale (last date: ${data[data.length - 1].date})`;
    badge.className = "badge bg-danger";
  }
}

function drawCharts(data) {
  new Chart(document.getElementById("revenueChart"), {
    type: "line",
    data: {
      labels: data.map(d => d.date),
      datasets: [
        { label: "Revenue", data: data.map(d => d.revenue) },
        { label: "Net Revenue", data: data.map(d => d.net) }
      ]
    }
  });

  new Chart(document.getElementById("ordersChart"), {
    type: "bar",
    data: {
      labels: data.map(d => d.date),
      datasets: [{ label: "Orders", data: data.map(d => d.orders) }]
    }
  });
}

function sum(data, key) {
  return data.reduce((a, b) => a + b[key], 0);
}

function money(v) {
  return v.toLocaleString("en-US", { style: "currency", currency: "EUR" });
}
