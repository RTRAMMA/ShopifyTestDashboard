import requests
import csv
from datetime import datetime, timedelta
from collections import defaultdict
from zoneinfo import ZoneInfo
import os
import sys

# ================================
# CONFIGURATION (ENV VARS)
# ================================
STORE_NAME = os.getenv("SHOPIFY_STORE")
API_TOKEN = os.getenv("SHOPIFY_API_TOKEN")
API_VERSION = os.getenv("SHOPIFY_API_VERSION", "2026-01")

if not STORE_NAME or not API_TOKEN:
    print("❌ Missing SHOPIFY_STORE or SHOPIFY_API_TOKEN")
    sys.exit(1)

BASE_URL = f"https://{STORE_NAME}.myshopify.com/admin/api/{API_VERSION}"
ORDERS_ENDPOINT = f"{BASE_URL}/orders.json"

HEADERS = {
    "X-Shopify-Access-Token": API_TOKEN,
    "Content-Type": "application/json"
}

OUTPUT_FILE = "daily_summary.csv"

# ================================
# TIMEZONE (SHOPIFY REPORTING)
# ================================
STORE_TZ = ZoneInfo("Europe/Berlin")
now_berlin = datetime.now(STORE_TZ)
cutoff_date = now_berlin - timedelta(days=30)

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
    print("📅 Last 30 days (Berlin time)")
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
# PROCESS ORDERS (SHOPIFY-EXACT)
# ================================
def process_orders(orders):
    daily_data = defaultdict(lambda: {
        "revenue": 0.0,
        "refunds": 0.0,
        "orders": 0
    })

    # ------------------------------------------------
    # 1️⃣ PRE-FILL ALL DAYS (INCL. ZERO-ORDER DAYS)
    # ------------------------------------------------
    start_date = cutoff_date.date()
    end_date = now_berlin.date()

    current_date = start_date
    while current_date <= end_date:
        daily_data[current_date.strftime("%Y-%m-%d")]
        current_date += timedelta(days=1)

    kept = 0
    excluded = 0

    # ------------------------------------------------
    # 2️⃣ APPLY SHOPIFY ANALYTICS FILTERS
    # ------------------------------------------------
    for order in orders:
        # ❌ Exclude test orders
        if order.get("test"):
            excluded += 1
            continue

        # ❌ Exclude unpaid orders
        if order.get("financial_status") != "paid":
            excluded += 1
            continue

        # ❌ Exclude cancelled orders
        if order.get("cancelled_at"):
            excluded += 1
            continue

        created_utc = datetime.fromisoformat(
            order["created_at"].replace("Z", "+00:00")
        )
        created_berlin = created_utc.astimezone(STORE_TZ)

        if created_berlin < cutoff_date:
            continue

        date_key = created_berlin.strftime("%Y-%m-%d")

        daily_data[date_key]["orders"] += 1
        daily_data[date_key]["revenue"] += float(order["total_price"])

        for refund in order.get("refunds", []):
            for tx in refund.get("transactions", []):
                if tx.get("kind") == "refund":
                    daily_data[date_key]["refunds"] += float(tx["amount"])

        kept += 1

    print(f"📦 Orders kept: {kept}")
    print(f"🚫 Orders excluded (Shopify rules): {excluded}")
    print(f"📅 Days generated: {len(daily_data)}")

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
            "order_count"
        ])

        for date in sorted(daily_data.keys()):
            revenue = daily_data[date]["revenue"]
            refunds = daily_data[date]["refunds"]
            writer.writerow([
                date,
                round(revenue, 2),
                round(refunds, 2),
                round(revenue - refunds, 2),
                daily_data[date]["orders"]
            ])

# ================================
# MAIN
# ================================
def main():
    orders = fetch_all_orders()
    print(f"📦 Total orders fetched (raw): {len(orders)}")

    daily_data = process_orders(orders)
    write_csv(daily_data)

    print("=" * 40)
    print(f"✅ CSV generated: {OUTPUT_FILE}")
    print("=" * 40)

if __name__ == "__main__":
    main()
