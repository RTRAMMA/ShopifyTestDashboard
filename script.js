fetch("./daily_summary.csv")
  .then(r => r.text())
  .then(csv => {
    const data = parseCSV(csv);
    setupDashboard(data);
    updateLastUpdatedStatus(data); // ✅ NEW
  });

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

/* ================================
   ✅ NEW: LAST UPDATED STATUS ONLY
   ================================ */
function updateLastUpdatedStatus(data) {
  if (!data || data.length === 0) return;

  const badge = document.getElementById("updateBadge");
  const lastDateStr = data[data.length - 1].date;

  const lastDate = new Date(lastDateStr);
  const today = new Date();

  lastDate.setHours(0,0,0,0);
  today.setHours(0,0,0,0);

  const diffDays = Math.round(
    (today - lastDate) / (1000 * 60 * 60 * 24)
  );

  if (diffDays === 0) {
    badge.textContent = `✅ Data up to date (last date: ${lastDateStr})`;
    badge.className = "badge bg-success";
  } else if (diffDays === 1) {
    badge.textContent = `🟡 Data from yesterday (${lastDateStr})`;
    badge.className = "badge bg-warning text-dark";
  } else {
    badge.textContent = `🔴 Data stale (last date: ${lastDateStr})`;
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
      datasets: [
        { label: "Orders", data: data.map(d => d.orders) }
      ]
    }
  });
}

function sum(data, key) {
  return data.reduce((a, b) => a + b[key], 0);
}

function money(v) {
  return v.toLocaleString("en-US", {
    style: "currency",
    currency: "EUR"
  });
}
