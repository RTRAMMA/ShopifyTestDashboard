import requests
import csv
from datetime import datetime, timedelta
from collections import defaultdict
from zoneinfo import ZoneInfo
import os
import sys
import time

# ================================
# CONFIGURATION
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
# TIMEZONE (BERLIN)
# ================================
STORE_TZ = ZoneInfo("Europe/Berlin")
now_berlin = datetime.now(STORE_TZ)
cutoff_date = now_berlin - timedelta(days=30)

# ================================
# FETCH ALL ORDERS
# ================================
def fetch_all_orders():
    orders = []
    url = ORDERS_ENDPOINT
    params = {
        "status": "any",
        "limit": 250,
        "order": "created_at desc"
    }

    while url:
        r = requests.get(url, headers=HEADERS, params=params, timeout=30)
        r.raise_for_status()
        data = r.json()
        orders.extend(data.get("orders", []))
        params = None

        link = r.headers.get("Link")
        url = None
        if link:
            for part in link.split(","):
                if 'rel="next"' in part:
                    url = part.split(";")[0].strip("<> ")

    return orders

# ================================
# FETCH REFUNDS FOR ONE ORDER
# ================================
def fetch_refunds(order_id):
    url = f"{BASE_URL}/orders/{order_id}/refunds.json"
    r = requests.get(url, headers=HEADERS, timeout=30)
    r.raise_for_status()
    return r.json().get("refunds", [])

# ================================
# PROCESS DATA
# ================================
def process_orders(orders):
    daily = defaultdict(lambda: {
        "revenue": 0.0,
        "refunds": 0.0,
        "orders": 0
    })

    # Pre-fill all days (0-order days included)
    d = cutoff_date.date()
    while d <= now_berlin.date():
        daily[d.strftime("%Y-%m-%d")]
        d += timedelta(days=1)

    refunded_orders = 0

    for order in orders:
        # Shopify Analytics filters
        if order.get("test"):
            continue
        if order.get("financial_status") != "paid":
            continue
        if order.get("cancelled_at"):
            continue

        created_utc = datetime.fromisoformat(
            order["created_at"].replace("Z", "+00:00")
        )
        created_berlin = created_utc.astimezone(STORE_TZ)

        if created_berlin < cutoff_date:
            continue

        order_day = created_berlin.strftime("%Y-%m-%d")
        daily[order_day]["orders"] += 1
        daily[order_day]["revenue"] += float(order["total_price"])

        # -----------------------------
        # REFUNDS (by refund date)
        # -----------------------------
        refunds = fetch_refunds(order["id"])
        if refunds:
            refunded_orders += 1

        for refund in refunds:
            for tx in refund.get("transactions", []):
                if tx.get("kind") == "refund":
                    refund_utc = datetime.fromisoformat(
                        tx["created_at"].replace("Z", "+00:00")
                    )
                    refund_berlin = refund_utc.astimezone(STORE_TZ)

                    if refund_berlin < cutoff_date:
                        continue

                    refund_day = refund_berlin.strftime("%Y-%m-%d")
                    daily[refund_day]["refunds"] += float(tx["amount"])

        # Rate-limit safety (Shopify friendly)
        time.sleep(0.15)

    print(f"🔁 Orders with refunds fetched: {refunded_orders}")
    return daily

# ================================
# WRITE CSV
# ================================
def write_csv(data):
    with open(OUTPUT_FILE, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["date", "revenue", "refunds", "net_revenue", "order_count"])

        for d in sorted(data.keys()):
            rev = data[d]["revenue"]
            ref = data[d]["refunds"]
            w.writerow([
                d,
                round(rev, 2),
                round(ref, 2),
                round(rev - ref, 2),
                data[d]["orders"]
            ])

# ================================
# MAIN
# ================================
def main():
    orders = fetch_all_orders()
    print(f"📦 Orders fetched: {len(orders)}")

    data = process_orders(orders)
    write_csv(data)

    print("✅ CSV generated:", OUTPUT_FILE)

if __name__ == "__main__":
    main()
