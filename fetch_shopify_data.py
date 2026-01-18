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

if not STORE_NAME or not API_TOKEN:
    print("❌ Missing SHOPIFY_STORE or SHOPIFY_API_TOKEN")
    sys.exit(1)

STORE_TZ = ZoneInfo("Europe/Berlin")

BASE_URL = f"https://{STORE_NAME}.myshopify.com/admin/api/{API_VERSION}"
ORDERS_ENDPOINT = f"{BASE_URL}/orders.json"

HEADERS = {
    "X-Shopify-Access-Token": API_TOKEN,
    "Content-Type": "application/json"
}

OUTPUT_FILE = "daily_summary.csv"
EXCLUDED_FILE = "excluded_orders.csv"

# ================================
# DATE RANGE (MATCH SHOPIFY UI)
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
    print("=" * 50)
    print("🛒 Fetching Shopify orders")
    print("🕒 Store timezone:", STORE_TZ)
    print("=" * 50)

    while url:
        response = requests.get(url, headers=HEADERS, params=params, timeout=30)
        response.raise_for_status()

        data = response.json()
        batch = data.get("orders", [])
        orders.extend(batch)

        print(f"✅ Page {page}: fetched {len(batch)} orders (total {len(orders)})")

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
# PROCESS ORDERS (ANALYTICS + DEBUG)
# ================================
def process_orders(orders):
    daily_data = defaultdict(lambda: {
        "revenue": 0.0,
        "orders": 0
    })

    excluded = []

    for order in orders:
        reason = None

        # ---- Analytics exclusion rules ----
        if order.get("test"):
            reason = "test_order"

        elif order.get("cancelled_at"):
            reason = "cancelled_order"

        elif order.get("financial_status") not in ("paid", "partially_paid"):
            reason = f"financial_status={order.get('financial_status')}"

        elif not order.get("processed_at"):
            reason = "no_processed_at"

        if reason:
            excluded.append({
                "order_id": order.get("id"),
                "order_name": order.get("name"),
                "created_at": order.get("created_at"),
                "processed_at": order.get("processed_at"),
                "financial_status": order.get("financial_status"),
                "total_price": order.get("total_price"),
                "excluded_reason": reason
            })
            continue

        # ---- Date bucketing (Shopify Analytics style) ----
        processed_utc = datetime.fromisoformat(
            order["processed_at"].replace("Z", "+00:00")
        )
        processed_berlin = processed_utc.astimezone(STORE_TZ)
        order_date = processed_berlin.date()

        if not (start_date <= order_date <= today_berlin):
            continue

        key = order_date.isoformat()
        daily_data[key]["orders"] += 1
        daily_data[key]["revenue"] += float(order["total_price"])

    return daily_data, excluded

# ================================
# WRITE DAILY CSV
# ================================
def write_daily_csv(daily_data):
    with open(OUTPUT_FILE, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["date", "revenue", "orders"])

        for date in sorted(daily_data.keys()):
            writer.writerow([
                date,
                round(daily_data[date]["revenue"], 2),
                daily_data[date]["orders"]
            ])

# ================================
# WRITE EXCLUDED CSV (MOST IMPORTANT)
# ================================
def write_excluded_csv(excluded):
    with open(EXCLUDED_FILE, "w", newline="", encoding="utf-8") as f:
        if not excluded:
            writer = csv.writer(f)
            writer.writerow(["no_excluded_orders"])
            return

        writer = csv.DictWriter(f, fieldnames=excluded[0].keys())
        writer.writeheader()
        writer.writerows(excluded)

# ================================
# MAIN
# ================================
def main():
    orders = fetch_all_orders()
    print(f"📦 Total orders fetched from API: {len(orders)}")

    daily_data, excluded = process_orders(orders)

    write_daily_csv(daily_data)
    write_excluded_csv(excluded)

    print("=" * 50)
    print(f"✅ Daily report written to: {OUTPUT_FILE}")
    print(f"🚫 Excluded orders written to: {EXCLUDED_FILE}")
    print("🔎 OPEN excluded_orders.csv to see EXACT reasons")
    print("=" * 50)

if __name__ == "__main__":
    main()
