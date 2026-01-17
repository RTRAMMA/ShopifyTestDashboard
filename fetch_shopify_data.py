import requests
import csv
from datetime import datetime, timedelta, timezone
from collections import defaultdict
import os
import sys

# ================================
# CONFIG (FROM ENV VARS)
# ================================
STORE = os.getenv("SHOPIFY_STORE")
TOKEN = os.getenv("SHOPIFY_API_TOKEN")
VERSION = os.getenv("SHOPIFY_API_VERSION", "2026-01")

if not STORE or not TOKEN:
    print("❌ Missing SHOPIFY_STORE or SHOPIFY_API_TOKEN")
    sys.exit(1)

BASE_URL = f"https://{STORE}.myshopify.com/admin/api/{VERSION}/orders.json"

HEADERS = {
    "X-Shopify-Access-Token": TOKEN,
    "Content-Type": "application/json"
}

# ================================
# LIMITS & FILTERS
# ================================
DAYS_RANGE = 30
MAX_ORDERS = 3000
LIMIT = 250
OUTPUT_FILE = "daily_summary.csv"

cutoff_date = datetime.now(timezone.utc) - timedelta(days=DAYS_RANGE)

# ================================
# FETCH ORDERS
# ================================
def fetch_orders():
    orders = []
    page_info = None
    page = 1
    first_request = True

    print("=" * 40)
    print("🛒 Fetching Shopify orders")
    print(f"📅 Date filter: last {DAYS_RANGE} days")
    print(f"🧯 Order safety cap: {MAX_ORDERS}")
    print("=" * 40)

    while True:
        params = {"limit": LIMIT}

        if first_request:
            params["status"] = "any"
        else:
            params = {"limit": LIMIT, "page_info": page_info}

        try:
            resp = requests.get(
                BASE_URL,
                headers=HEADERS,
                params=params,
                timeout=30
            )
        except Exception as e:
            print(f"❌ Network error: {e}")
            sys.exit(1)

        if resp.status_code != 200:
            print(f"❌ Shopify API error {resp.status_code}")
            print(resp.text)
            sys.exit(1)

        batch = resp.json().get("orders", [])
        if not batch:
            print("ℹ️ No more orders returned.")
            break

        for order in batch:
            created = datetime.fromisoformat(
                order["created_at"].replace("Z", "+00:00")
            )

            if created < cutoff_date:
                print("🛑 Reached orders older than cutoff date.")
                return orders

            orders.append(order)

            if len(orders) >= MAX_ORDERS:
                print("🛑 Reached max order cap. Stopping fetch.")
                return orders

        print(f"✅ Page {page}: total orders = {len(orders)}")
        page += 1
        first_request = False

        link = resp.headers.get("Link")
        if not link or 'rel="next"' not in link:
            print("ℹ️ No next page found.")
            break

        page_info = link.split("page_info=")[1].split(">")[0]

    return orders

# ================================
# PROCESS TO DAILY SUMMARY
# ================================
def process_orders(orders):
    daily = defaultdict(lambda: {
        "revenue": 0.0,
        "refunds": 0.0,
        "order_count": 0
    })

    for order in orders:
        date_key = order["created_at"][:10]
        revenue = float(order["total_price"])

        daily[date_key]["revenue"] += revenue
        daily[date_key]["order_count"] += 1

        for refund in order.get("refunds", []):
            for tx in refund.get("transactions", []):
                if tx.get("kind") == "refund":
                    daily[date_key]["refunds"] += float(tx["amount"])

    return daily

# ================================
# WRITE CSV
# ================================
def write_csv(daily_data):
    with open(OUTPUT_FILE, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow([
            "date",
            "revenue",
            "refunds",
            "net_revenue",
            "order_count"
        ])

        for d in sorted(daily_data.keys()):
            r = daily_data[d]
            writer.writerow([
                d,
                round(r["revenue"], 2),
                round(r["refunds"], 2),
                round(r["revenue"] - r["refunds"], 2),
                r["order_count"]
            ])

# ================================
# MAIN
# ================================
def main():
    orders = fetch_orders()
    print("=" * 40)
    print(f"📦 Orders processed: {len(orders)}")
    print("=" * 40)

    daily = process_orders(orders)
    write_csv(daily)

    print("========================================")
    print(f"📄 CSV generated: {OUTPUT_FILE}")
    print("========================================")

if __name__ == "__main__":
    main()
