import requests
import csv
from datetime import datetime, timedelta, timezone
from collections import defaultdict
import os
import sys

# ================================
# CONFIG (ENV VARS)
# ================================
STORE = os.getenv("SHOPIFY_STORE")
TOKEN = os.getenv("SHOPIFY_API_TOKEN")
VERSION = os.getenv("SHOPIFY_API_VERSION", "2026-01")

if not STORE or not TOKEN:
    print("❌ Missing SHOPIFY_STORE or SHOPIFY_API_TOKEN")
    sys.exit(1)

ORDERS_URL = f"https://{STORE}.myshopify.com/admin/api/{VERSION}/orders.json"

HEADERS = {
    "X-Shopify-Access-Token": TOKEN,
    "Content-Type": "application/json"
}

# ================================
# LIMITS
# ================================
MAX_ORDERS = 10000
LIMIT = 250
DAYS_RANGE = 30
OUTPUT_FILE = "daily_summary.csv"

cutoff_date = datetime.now(timezone.utc) - timedelta(days=DAYS_RANGE)

# ================================
# FETCH ORDERS (NO DATE STOP!)
# ================================
def fetch_orders():
    orders = []
    page_info = None
    page = 1
    first = True

    print("=" * 40)
    print("🛒 Fetching Shopify orders")
    print(f"🧯 Max orders: {MAX_ORDERS}")
    print("=" * 40)

    while len(orders) < MAX_ORDERS:
        params = {"limit": LIMIT}

        if first:
            params["status"] = "any"
            params["order"] = "created_at desc"
        else:
            params = {"limit": LIMIT, "page_info": page_info}

        resp = requests.get(
            ORDERS_URL,
            headers=HEADERS,
            params=params,
            timeout=30
        )

        if resp.status_code != 200:
            print(f"❌ Shopify API error {resp.status_code}")
            print(resp.text)
            sys.exit(1)

        batch = resp.json().get("orders", [])
        if not batch:
            break

        orders.extend(batch)
        print(f"✅ Page {page}: fetched {len(orders)} orders so far")

        link = resp.headers.get("Link")
        if not link or 'rel="next"' not in link:
            break

        page_info = link.split("page_info=")[1].split(">")[0]
        first = False
        page += 1

    return orders[:MAX_ORDERS]

# ================================
# FILTER + AGGREGATE
# ================================
def process_orders(orders):
    daily = defaultdict(lambda: {
        "revenue": 0.0,
        "refunds": 0.0,
        "order_count": 0
    })

    kept = 0

    for o in orders:
        created = datetime.fromisoformat(o["created_at"].replace("Z", "+00:00"))
        if created < cutoff_date:
            continue

        date_key = created.astimezone(timezone.utc).strftime("%Y-%m-%d")
        revenue = float(o["total_price"])

        refunds = sum(
            float(t["amount"])
            for r in o.get("refunds", [])
            for t in r.get("transactions", [])
            if t.get("kind") == "refund"
        )

        daily[date_key]["revenue"] += revenue
        daily[date_key]["refunds"] += refunds
        daily[date_key]["order_count"] += 1
        kept += 1

    print(f"📦 Orders within last 30 days: {kept}")
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
    orders = fetch_orders()
    print(f"📦 Total orders fetched: {len(orders)}")

    daily = process_orders(orders)
    write_csv(daily)

    print("========================================")
    print("✅ CSV generated: daily_summary.csv")
    print("========================================")

if __name__ == "__main__":
    main()

