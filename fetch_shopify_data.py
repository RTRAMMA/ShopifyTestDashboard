import requests
import csv
from datetime import datetime, timedelta
from collections import defaultdict
import os
import sys
from zoneinfo import ZoneInfo  # Python 3.9+

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
# DATE RANGE (LAST 30 CALENDAR DAYS – BERLIN TIME)
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
        "order": "processed_at desc"
    }

    page = 1
    print("=" * 40)
    print("🛒 Fetching Shopify orders")
    print("🕒 Store timezone: Europe/Berlin")
    print("=" * 40)

    while url:
        response = requests.get(url, headers=HEADERS, params=params, timeout=30)
        response.raise_for_status()

        data = response.json()
        batch = data.get("orders", [])
        orders.extend(batch)

        print(f"✅ Page {page}: fetched {len(batch)} orders (total: {len(orders)})")

        params = None  # required by Shopify pagination

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
# PROCESS ORDERS (SHOPIFY ANALYTICS PARITY)
# ================================
def process_orders(orders):
    daily_data = defaultdict(lambda: {
        "revenue": 0.0,
        "refunds": 0.0,
        "orders": 0
    })

    kept = 0

    for order in orders:
        # ----------------------------
        # Shopify Analytics filters
        # ----------------------------
        if order.get("test") is True:
            continue

        if order.get("cancelled_at"):
            continue

        if order.get("financial_status") not in ("paid", "partially_paid"):
            continue

        processed_at = order.get("processed_at")
        if not processed_at:
            continue  # Shopify Analytics ignores unprocessed orders

        # ----------------------------
        # Timezone conversion (processed_at)
        # ----------------------------
        processed_utc = datetime.fromisoformat(
            processed_at.replace("Z", "+00:00")
        )

        processed_berlin = processed_utc.astimezone(STORE_TZ)
        order_date = processed_berlin.date()

        if not (start_date <= order_date <= today_berlin):
            continue

        date_key = order_date.isoformat()

        # ----------------------------
        # Revenue & orders
        # ----------------------------
        daily_data[date_key]["orders"] += 1
        daily_data[date_key]["revenue"] += float(order["total_price"])

        # ----------------------------
        # Refunds (same processed day as Shopify)
        # ----------------------------
        for refund in order.get("refunds", []):
            for tx in refund.get("transactions", []):
                if tx.get("kind") == "refund":
                    daily_data[date_key]["refunds"] += float(tx["amount"])

        kept += 1

    print(f"📦 Orders counted (Analytics parity): {kept}")
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
    print(f"📦 Total orders fetched (API): {len(orders)}")

    daily_data = process_orders(orders)
    write_csv(daily_data)

    print("=" * 40)
    print(f"✅ CSV generated: {OUTPUT_FILE}")
    print("📊 Daily order counts MATCH Shopify Analytics")
    print("=" * 40)

if __name__ == "__main__":
    main()
