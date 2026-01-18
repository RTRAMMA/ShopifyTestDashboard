import requests
import csv
from datetime import datetime, timedelta, timezone
from collections import defaultdict
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

ORDERS_ENDPOINT = f"https://{STORE_NAME}.myshopify.com/admin/api/{API_VERSION}/orders.json"

HEADERS = {
    "X-Shopify-Access-Token": API_TOKEN,
    "Content-Type": "application/json"
}

OUTPUT_FILE = "daily_summary.csv"
CUTOFF_DATE = datetime.now(timezone.utc) - timedelta(days=30)

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
    print("🛒 Fetching Shopify orders (all-time, paginated)")
    print("📅 Filtering to last 30 days AFTER fetch")
    print("=" * 40)

    while url:
        try:
            resp = requests.get(url, headers=HEADERS, params=params, timeout=30)
            resp.raise_for_status()
        except Exception as e:
            print(f"❌ API request failed on page {page}")
            print(e)
            sys.exit(1)

        data = resp.json()
        batch = data.get("orders", [])
        orders.extend(batch)

        print(f"✅ Page {page}: fetched {len(batch)} orders (total: {len(orders)})")

        # After first request, params MUST be None
        params = None

        # Parse pagination
        next_url = None
        link_header = resp.headers.get("Link")
        if link_header:
            for link in link_header.split(","):
                if 'rel="next"' in link:
                    next_url = link.split(";")[0].strip("<> ")

        url = next_url
        page += 1

    return orders

# ================================
# FILTER + AGGREGATE (BUSINESS-ALIGNED)
# ================================
def process_orders(orders):
    daily = defaultdict(lambda: {
        "revenue": 0.0,
        "refunds": 0.0,
        "order_count": 0
    })

    kept = 0

    for order in orders:
        # ✔ Only PAID orders (matches Admin)
        if order.get("financial_status") != "paid":
            continue

        # ✔ Exclude test orders
        if order.get("test"):
            continue

        # ✔ Use processed_at (matches Admin day grouping)
        processed_at = order.get("processed_at")
        if not processed_at:
            continue

        dt = datetime.fromisoformat(processed_at.replace("Z", "+00:00"))
        if dt < CUTOFF_DATE:
            continue

        date_key = dt.strftime("%Y-%m-%d")

        revenue = float(order.get("total_price", 0.0))
        daily[date_key]["revenue"] += revenue
        daily[date_key]["order_count"] += 1

        # Refunds (keep as-is)
        for refund in order.get("refunds", []):
            for tx in refund.get("transactions", []):
                if tx.get("kind") == "refund":
                    daily[date_key]["refunds"] += float(tx.get("amount", 0.0))

        kept += 1

    print(f"📦 Orders kept (paid, non-test, last 30 days): {kept}")
    return daily

# ================================
# WRITE CSV
# ================================
def write_csv(daily):
    with open(OUTPUT_FILE, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["date", "revenue", "refunds", "net_revenue", "order_count"])

        for d in sorted(daily.keys()):
            r = daily[d]
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
    orders = fetch_all_orders()
    print(f"📦 Total orders fetched (all-time): {len(orders)}")

    daily = process_orders(orders)
    write_csv(daily)

    print("=" * 40)
    print("✅ CSV generated: daily_summary.csv")
    print("=" * 40)

if __name__ == "__main__":
    main()
