import requests
import csv
from datetime import datetime, timedelta, timezone
from collections import defaultdict
import os

STORE = os.getenv("SHOPIFY_STORE")
TOKEN = os.getenv("SHOPIFY_API_TOKEN")
VERSION = os.getenv("SHOPIFY_API_VERSION", "2026-01")

DAYS_RANGE = 30
MAX_ORDERS = 1000
LIMIT = 250

HEADERS = {
    "X-Shopify-Access-Token": TOKEN
}

cutoff_date = datetime.now(timezone.utc) - timedelta(days=DAYS_RANGE)

print("========================================")
print("🛒 Fetching Shopify orders")
print(f"📅 Date filter: last {DAYS_RANGE} days")
print(f"🧯 Order safety cap: {MAX_ORDERS}")
print("========================================")

orders = []
page_info = None

while len(orders) < MAX_ORDERS:
    params = {
        "limit": LIMIT,
        "status": "any",
        "order": "created_at desc"
    }

    if page_info:
        params["page_info"] = page_info

    resp = requests.get(
        f"https://{STORE}.myshopify.com/admin/api/{VERSION}/orders.json",
        headers=HEADERS,
        params=params,
        timeout=30
    )

    if resp.status_code != 200:
        raise Exception(f"❌ Shopify API error {resp.status_code}: {resp.text}")

    batch = resp.json().get("orders", [])
    if not batch:
        break

    for o in batch:
        created = datetime.fromisoformat(o["created_at"].replace("Z", "+00:00"))
        if created < cutoff_date:
            page_info = None
            break
        orders.append(o)

    print(f"✅ Fetched {len(orders)} orders so far")

    link = resp.headers.get("Link")
    if not link or 'rel="next"' not in link:
        break

    page_info = link.split("page_info=")[1].split(">")[0]

    if len(orders) >= MAX_ORDERS:
        print("🛑 Reached max order cap. Stopping fetch.")
        break

# ================================
# DAILY AGGREGATION
# ================================

daily = defaultdict(lambda: {
    "revenue": 0.0,
    "refunds": 0.0,
    "order_count": 0
})

for o in orders:
    date_key = o["created_at"][:10]
    revenue = float(o["total_price"])
    refunds = sum(
        float(r["amount"])
        for r in o.get("refunds", [])
        for r in r.get("transactions", [])
    )

    daily[date_key]["revenue"] += revenue
    daily[date_key]["refunds"] += refunds
    daily[date_key]["order_count"] += 1

# ================================
# WRITE CSV
# ================================

with open("daily_summary.csv", "w", newline="", encoding="utf-8") as f:
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

print("========================================")
print("✅ Sync complete")
print(f"📦 Orders scanned: {len(orders)}")
print("📄 CSV generated: daily_summary.csv")
print("========================================")
