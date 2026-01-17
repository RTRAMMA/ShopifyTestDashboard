import requests
import csv
import os
from datetime import datetime, timedelta, timezone

# ==============================
# Environment variables
# ==============================
STORE_NAME = os.getenv("SHOPIFY_STORE")
API_TOKEN = os.getenv("SHOPIFY_API_TOKEN")
API_VERSION = os.getenv("SHOPIFY_API_VERSION", "2026-01")

if not STORE_NAME or not API_TOKEN:
    raise RuntimeError("Missing SHOPIFY_STORE or SHOPIFY_API_TOKEN")

HEADERS = {
    "X-Shopify-Access-Token": API_TOKEN
}

BASE_URL = f"https://{STORE_NAME}.myshopify.com/admin/api/{API_VERSION}/orders.json"

# ==============================
# Config
# ==============================
DAYS_RANGE = 30
START_DATE = datetime.now(timezone.utc) - timedelta(days=DAYS_RANGE)

# ==============================
# Fetch orders (FAST & SAFE)
# ==============================
def fetch_recent_orders():
    orders = []

    params = {
        "status": "any",
        "limit": 250,
        "created_at_min": START_DATE.isoformat()
    }

    page = 1

    while True:
        response = requests.get(
            BASE_URL,
            headers=HEADERS,
            params=params,
            timeout=30
        )

        response.raise_for_status()

        batch = response.json().get("orders", [])
        orders.extend(batch)

        print(f"Fetched page {page}, total orders so far: {len(orders)}")

        link = response.headers.get("Link")
        if link and 'rel="next"' in link:
            page_info = link.split("page_info=")[1].split(">")[0]
            params = {
                "limit": 250,
                "page_info": page_info
            }
            page += 1
        else:
            break

    return orders

# ==============================
# Generate summary CSV
# ==============================
def generate_daily_summary(orders):
    revenue = 0.0
    refunds = 0.0
    ad_spend = 0.0  # Manual input for now

    for order in orders:
        revenue += float(order.get("total_price", 0))

        for refund in order.get("refunds", []):
            for txn in refund.get("transactions", []):
                refunds += abs(float(txn.get("amount", 0)))

    net_profit = revenue - refunds - ad_spend
    roas = revenue / ad_spend if ad_spend > 0 else 0.0

    with open("daily_summary.csv", "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["metric", "value"])
        writer.writerow(["revenue", round(revenue, 2)])
        writer.writerow(["refunds", round(refunds, 2)])
        writer.writerow(["ad_spend", round(ad_spend, 2)])
        writer.writerow(["net_profit", round(net_profit, 2)])
        writer.writerow(["roas", round(roas, 2)])
        writer.writerow(["last_updated", datetime.now(timezone.utc).strftime("%Y-%m-%d")])
        writer.writerow(["data_range", f"Last {DAYS_RANGE} days"])

# ==============================
# Main
# ==============================
def main():
    print("========================================")
    print("Fetching Shopify orders (last 30 days)...")
    print("========================================")

    orders = fetch_recent_orders()
    generate_daily_summary(orders)

    print("========================================")
    print(f"Total orders processed: {len(orders)}")
    print("CSV generated: daily_summary.csv")
    print("========================================")

if __name__ == "__main__":
    main()
