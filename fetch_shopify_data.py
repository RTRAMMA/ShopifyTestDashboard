import requests
import csv
from datetime import datetime
from collections import defaultdict
import os
from zoneinfo import ZoneInfo

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

def fetch_orders():
    orders = []
    url = ORDERS_URL
    params = {
        "limit": 250,
        "status": "any",
        "order": "processed_at asc"
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

def main():
    orders = fetch_orders()
    daily = defaultdict(lambda: {"revenue": 0, "refunds": 0, "orders": 0})

    for o in orders:
        if o.get("test") or o.get("cancelled_at"):
            continue
        if o.get("financial_status") not in ("paid", "partially_paid"):
            continue
        if not o.get("processed_at"):
            continue

        dt = datetime.fromisoformat(o["processed_at"].replace("Z", "+00:00"))
        dt = dt.astimezone(STORE_TZ).date()
        key = dt.isoformat()

        daily[key]["orders"] += 1
        daily[key]["revenue"] += float(o["total_price"])

        for refund in o.get("refunds", []):
            for tx in refund.get("transactions", []):
                if tx.get("kind") == "refund":
                    daily[key]["refunds"] += float(tx["amount"])

    with open("daily_summary.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["date", "revenue", "refunds", "net_revenue", "order_count"])
        for d in sorted(daily):
            rev = round(daily[d]["revenue"], 2)
            ref = round(daily[d]["refunds"], 2)
            net = round(rev - ref, 2)
            w.writerow([d, rev, ref, net, daily[d]["orders"]])

if __name__ == "__main__":
    main()
