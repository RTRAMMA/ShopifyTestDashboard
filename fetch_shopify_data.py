import requests
import csv
import os
from datetime import datetime, timedelta, timezone

# --- ENV VARIABLES (from GitHub Secrets or local env) ---
STORE_NAME = os.getenv("SHOPIFY_STORE")
API_TOKEN = os.getenv("SHOPIFY_API_TOKEN")
API_VERSION = os.getenv("SHOPIFY_API_VERSION", "2026-01")

HEADERS = {
    "X-Shopify-Access-Token": API_TOKEN
}

BASE_URL = f"https://{STORE_NAME}.myshopify.com/admin/api/{API_VERSION}/orders.json"

DAYS_RANGE = 30
START_DATE = datetime.now(timezone.utc) - timedelta(days=DAYS_RANGE)

def fetch_all_orders():
    orders = []
    params = {
        "status": "any",
        "limit": 250
    }

    while True:
        response = requests.get(
            BASE_URL,
            headers=HEADERS,
            params=params,
            timeout=30
        )
        response.raise_for_status()

        data = response.json().get("orders", [])
        orders.extend(data)

        link = response.headers.get("Link")
        if link and 'rel="next"' in link:
            page_info = link.split("page_info=")[1].split(">")[0]
            params = {
                "limit": 250,
                "page_info": page_info
            }
        else:
            break

    return orders

def generate_daily_summary(orders):
    revenue = 0.0
    refunds = 0.0

    for order in orders:
        created_at = datetime.fromisoformat(order["created_at"].replace("Z", "+00:00"))
        if created_at < START_DATE:
            continue

        revenue += float(order.get("total_price", 0))

        for refund in order.get("refunds", []):
            for txn in refund.get("transactions", []):
                refunds += abs(float(txn.get("amount", 0)))

    ad_spend = 0.0
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

    print("========================================")
    print(f"Fetched {len(orders)} orders")
    print("CSV generated: daily_summary.csv")
    print("========================================")

def main():
    print("Fetching Shopify orders...")
    orders = fetch_all_orders()
    generate_daily_summary(orders)

if __name__ == "__main__":
    main()
