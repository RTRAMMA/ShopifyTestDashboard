let revenueChart;
let ordersChart;

// -------------------------------
// LOAD CSV
// -------------------------------
fetch("./daily_summary.csv")
  .then(r => r.text())
  .then(csv => {
    const data = parseCSV(csv);
    setupDashboard(data);
  });

// -------------------------------
// CSV PARSER
// -------------------------------
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

// -------------------------------
// DASHBOARD SETUP
// -------------------------------
function setupDashboard(data) {
  const adInput = document.getElementById("adSpendInput");

  function recalc() {
    updateSummary(
      sum(data, "revenue"),
      sum(data, "refunds"),
      parseFloat(adInput.value) || 0
    );
  }

  drawCharts(data);
  recalc();
  adInput.addEventListener("input", recalc);
}

// -------------------------------
// SUMMARY
// -------------------------------
function updateSummary(revenue, refunds, adSpend) {
  const net = revenue - refunds - adSpend;
  const roas = adSpend > 0 ? revenue / adSpend : null;

  document.getElementById("totalRevenue").innerText = money(revenue);
  document.getElementById("totalRefunds").innerText = money(refunds);
  document.getElementById("adSpend").innerText = money(adSpend);
  document.getElementById("netProfit").innerText = money(net);

  const roasEl = document.getElementById("roas");
  const statusEl = document.getElementById("status");
  statusEl.className = "";

  if (adSpend === 0) {
    roasEl.innerText = "—";
    statusEl.innerText = "N/A";
    statusEl.classList.add("status-na");
  } else {
    roasEl.innerText = roas.toFixed(2);

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
}

// -------------------------------
// CHARTS
// -------------------------------
function drawCharts(data) {
  const labels = data.map(d => d.date);

  revenueChart = new Chart(document.getElementById("revenueChart"), {
    type: "line",
    data: {
      labels,
      datasets: [
        { label: "Revenue (€)", data: data.map(d => d.revenue), tension: 0.3 },
        { label: "Net Revenue (€)", data: data.map(d => d.net), tension: 0.3 }
      ]
    }
  });

  ordersChart = new Chart(document.getElementById("ordersChart"), {
    type: "bar",
    data: {
      labels,
      datasets: [{ label: "Orders", data: data.map(d => d.orders) }]
    }
  });
}

// -------------------------------
// SYNC STATUS (POLLING)
// -------------------------------
function updateSyncStatus() {
  fetch("./sync_status.json")
    .then(r => r.json())
    .then(d => {
      const badge = document.getElementById("syncBadge");
      const ts = document.getElementById("lastUpdated");

      if (d.status === "syncing") {
        badge.innerText = "🔄 Data syncing…";
        badge.className = "badge bg-warning text-dark";
        ts.innerText = "";
      } else {
        badge.innerText = "✅ Data up to date";
        badge.className = "badge bg-success";
        ts.innerText = "Last updated: " + d.last_updated;

        // 🔓 Re-enable button when done
        if (refreshBtn) {
          refreshBtn.disabled = false;
          refreshBtn.innerText = "🔄 Refresh Data";
          refreshMsg.innerText = "";
        }
      }
    })
    .catch(() => {});
}

updateSyncStatus();
setInterval(updateSyncStatus, 5000);

// -------------------------------
// MANUAL REFRESH BUTTON (UPDATED)
// -------------------------------
const refreshBtn = document.getElementById("refreshBtn");
const refreshMsg = document.getElementById("refreshMsg");

if (refreshBtn) {
  refreshBtn.addEventListener("click", async () => {
    refreshBtn.disabled = true;
    refreshBtn.innerText = "⏳ Refreshing…";
    refreshMsg.innerText = "Refresh started ✔";

    // ⭐ IMMEDIATE optimistic UI update
    document.getElementById("syncBadge").innerText = "🔄 Data syncing…";
    document.getElementById("syncBadge").className =
      "badge bg-warning text-dark";
    document.getElementById("lastUpdated").innerText = "";

    try {
      await fetch(
       "https://api.github.com/repos/RTRAMMA/ShopifyTestDashboard/actions/workflows/daily_update.yml/dispatches",
        {
          method: "POST",
          headers: {
            Accept: "application/vnd.github+json",
            "Authorization": "Bearer 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"
          },
          body: JSON.stringify({ ref: "main" })
        }
      );
    } catch (e) {
      refreshMsg.innerText = "Failed to trigger refresh ❌";
      refreshBtn.disabled = false;
      refreshBtn.innerText = "🔄 Refresh Data";
    }
  });
}

// -------------------------------
// HELPERS
// -------------------------------
function sum(data, key) {
  return data.reduce((a, b) => a + b[key], 0);
}

function money(v) {
  return v.toLocaleString("en-US", {
    style: "currency",
    currency: "EUR"
  });
}

