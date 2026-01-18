import requests
import csv
from datetime import datetime
from collections import defaultdict
import os
from zoneinfo import ZoneInfo

# ================================
# CONFIG
# ================================
STORE_NAME = os.getenv("SHOPIFY_STORE")
API_TOKEN = os.getenv("SHOPIFY_API_TOKEN")
API_VERSION = "2026-01"

STORE_TZ = ZoneInfo("Europe/Berlin")

BASE_URL = f"https://{STORE_NAME}.myshopify.com/admin/api/{API_VERSION}"
ORDERS_URL = f"{BASE_URL}/orders.json"

HEADERS = {
    "X-Shopify-Access-Token": API_TOKEN,
    "Content-Type": "application/json"
}

# ================================
# FETCH ORDERS (WITH TRANSACTIONS)
# ================================
def fetch_orders():
    orders = []
    url = ORDERS_URL
    params = {
        "limit": 250,
        "status": "any",
        "order": "processed_at asc",
        "fields": (
            "id,processed_at,test,cancelled_at,financial_status,"
            "total_price,transactions"
        )
    }

    while url:
        r = requests.get(url, headers=HEADERS, params=params)
        r.raise_for_status()
        data = r.json()
        orders.extend(data["orders"])

        params = None
        link = r.headers.get("Link")
        next_url = None
        if link:
            for part in link.split(","):
                if 'rel="next"' in part:
                    next_url = part.split(";")[0].strip("<> ")
        url = next_url

    return orders

# ================================
# MAIN
# ================================
def main():
    orders = fetch_orders()

    daily = defaultdict(lambda: {
        "revenue": 0.0,
        "refunds": 0.0,
        "orders": 0
    })

    for o in orders:
        # ---- Shopify Analytics filters ----
        if o.get("test"):
            continue
        if o.get("cancelled_at"):
            continue
        if o.get("financial_status") not in ("paid", "partially_paid"):
            continue
        if not o.get("processed_at"):
            continue

        # ---- Date bucket (Berlin time) ----
        dt = datetime.fromisoformat(
            o["processed_at"].replace("Z", "+00:00")
        ).astimezone(STORE_TZ).date()

        key = dt.isoformat()

        # ---- Orders & revenue ----
        daily[key]["orders"] += 1
        daily[key]["revenue"] += float(o["total_price"])

        # ---- REFUNDS (FIXED) ----
        for tx in o.get("transactions", []):
            if tx.get("kind") == "refund":
                daily[key]["refunds"] += float(tx["amount"])

    # ================================
    # WRITE CSV
    # ================================
    with open("daily_summary.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["date", "revenue", "refunds", "net_revenue", "order_count"])
        for d in sorted(daily):
            rev = round(daily[d]["revenue"], 2)
            ref = round(daily[d]["refunds"], 2)
            net = round(rev - ref, 2)
            w.writerow([d, rev, ref, net, daily[d]["orders"]])

    print("✅ daily_summary.csv generated with refunds included")

if __name__ == "__main__":
    main()
