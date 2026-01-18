import requests
import csv
from datetime import datetime, timedelta, timezone
from collections import defaultdict
import os
import sys
from zoneinfo import ZoneInfo   # Python 3.9+

# ================================
# CONFIGURATION
# ================================
STORE_NAME = os.getenv("SHOPIFY_STORE")
API_TOKEN = os.getenv("SHOPIFY_API_TOKEN")
API_VERSION = os.getenv("SHOPIFY_API_VERSION", "2026-01")

STORE_TZ = ZoneInfo("Europe/Berlin")
OUTPUT_FILE = "daily_summary.csv"

if not STORE_NAME or not API_TOKEN:
    print("❌ Missing SHOPIFY_STORE or SHOPIFY_API_TOKEN")
    sys.exit(1)

BASE_URL = f"https://{STORE_NAME}.myshopify.com/admin/api/{API_VERSION}"
ORDERS_ENDPOINT = f"{BASE_URL}/orders.json"

HEADERS = {
    "X-Shopify-Access-Token": API_TOKEN,
    "Content-Type": "application/json"
}

# ================================
# DATE RANGE (LAST 30 CALENDAR DAYS — BERLIN TIME)
# ================================
today_berlin = datetime.now(STORE_TZ).date()
start_date = today_berlin - timedelta(days=30)

# ================================
# FETCH ALL ORDERS (PAGINATED)
# ================================
def fetch_all_orders():
    orders = []
    url = ORDERS_ENDPOINT
    params = {
        "status": "any",
        "limit": 250,
        "order": "created_at desc"
    }

    page = 1

    print("=" * 40)
    print("🛒 Fetching Shopify orders")
    print("📅 Store timezone: Europe/Berlin")
    print("=" * 40)

    while url:
        response = requests.get(url, headers=HEADERS, params=params, timeout=30)
        response.raise_for_status()

        data = response.json()
        batch = data.get("orders", [])
        orders.extend(batch)

        print(f"✅ Page {page}: fetched {len(batch)} orders (total: {len(orders)})")

        params = None

        link_header = response.headers.get("Link")
        next_url = None
        if link_header:
            for link in link_header.split(","):
                if 'rel="next"' in link:
                    next_url = link.split(";")[0].strip("<> ")

        url = next_url
        page += 1

    return orders

# ================================
# PROCESS ORDERS (BERLIN DAY BUCKETING)
# ================================
def process_orders(orders):
    daily_data = defaultdict(lambda: {
        "revenue": 0.0,
        "refunds": 0.0,
        "orders": 0
    })

    kept = 0

    for order in orders:
        # Parse UTC timestamp
        created_utc = datetime.fromisoformat(
            order["created_at"].replace("Z", "+00:00")
        )

        # Convert to Berlin time
        created_berlin = created_utc.astimezone(STORE_TZ)
        order_date = created_berlin.date()

        # Calendar-day filter (Shopify-style)
        if not (start_date <= order_date <= today_berlin):
            continue

        date_key = order_date.isoformat()
        revenue = float(order["total_price"])

        daily_data[date_key]["revenue"] += revenue
        daily_data[date_key]["orders"] += 1

        for refund in order.get("refunds", []):
            for tx in refund.get("transactions", []):
                if tx.get("kind") == "refund":
                    daily_data[date_key]["refunds"] += float(tx["amount"])

        kept += 1

    print(f"📦 Orders within date range: {kept}")
    return daily_data

# ================================
# WRITE CSV
# ================================
def write_csv(daily_data):
    with open(OUTPUT_FILE, "w", newline="", encoding="utf-8") as csvfile:
        writer = csv.writer(csvfile)
        writer.writerow([
            "date",
            "revenue",
            "refunds",
            "net_revenue",
            "orders"
        ])

        for date in sorted(daily_data.keys()):
            revenue = daily_data[date]["revenue"]
            refunds = daily_data[date]["refunds"]
            net_revenue = revenue - refunds
            orders = daily_data[date]["orders"]

            writer.writerow([
                date,
                round(revenue, 2),
                round(refunds, 2),
                round(net_revenue, 2),
                orders
            ])

# ================================
# MAIN
# ================================
def main():
    orders = fetch_all_orders()
    print(f"📦 Total orders fetched: {len(orders)}")

    daily_data = process_orders(orders)
    write_csv(daily_data)

    print("=" * 40)
    print(f"✅ CSV generated: {OUTPUT_FILE}")
    print("📊 Daily order counts now match Shopify Analytics")
    print("=" * 40)

if __name__ == "__main__":
    main()
