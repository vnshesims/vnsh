#!/usr/bin/env python3
"""
VNSH Invoice Purge Script
Deletes invoices older than 24 hours from BTCPay Server.
Run frequently via cron (e.g., every hour) to maintain privacy.
"""

import os
import sys
import requests
from pathlib import Path
from datetime import datetime, timezone

# Load .env file if it exists
env_path = Path(__file__).parent.parent / '.env'
if env_path.exists():
    with open(env_path) as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith('#') and '=' in line:
                key, value = line.split('=', 1)
                if value and value != 'YOUR_STORE_ID_HERE' and value != 'YOUR_API_KEY_HERE':
                    os.environ.setdefault(key.strip(), value.strip())

# BTCPay Server configuration
BTCPAY_URL = os.environ.get('BTCPAY_URL', 'http://172.18.0.10:80')
BTCPAY_API_KEY = os.environ.get('BTCPAY_API_KEY', '')
BTCPAY_STORE_ID = os.environ.get('BTCPAY_STORE_ID', '')

# Invoice age threshold (24 hours in seconds)
MAX_AGE_SECONDS = 24 * 60 * 60


def get_all_invoices():
    """Fetch all invoices from BTCPay Server."""
    if not BTCPAY_API_KEY or not BTCPAY_STORE_ID:
        print("[ERROR] BTCPay API key or Store ID not configured")
        return []

    try:
        response = requests.get(
            f"{BTCPAY_URL}/api/v1/stores/{BTCPAY_STORE_ID}/invoices",
            headers={"Authorization": f"token {BTCPAY_API_KEY}"},
            timeout=30
        )
        if response.status_code == 200:
            return response.json()
        else:
            print(f"[ERROR] Failed to fetch invoices: {response.status_code}")
            return []
    except Exception as e:
        print(f"[ERROR] Error fetching invoices: {e}")
        return []


def delete_invoice(invoice_id):
    """Delete a single invoice from BTCPay Server."""
    try:
        response = requests.delete(
            f"{BTCPAY_URL}/api/v1/stores/{BTCPAY_STORE_ID}/invoices/{invoice_id}",
            headers={"Authorization": f"token {BTCPAY_API_KEY}"},
            timeout=10
        )
        return response.status_code in (200, 204)
    except Exception as e:
        print(f"[ERROR] Error deleting invoice {invoice_id}: {e}")
        return False


def parse_invoice_time(invoice):
    """Parse invoice creation time from BTCPay response."""
    # BTCPay returns createdTime as Unix timestamp (seconds)
    created_time = invoice.get('createdTime')
    if created_time:
        return datetime.fromtimestamp(created_time, tz=timezone.utc)
    return None


def purge_old_invoices():
    """Purge invoices older than 24 hours from BTCPay Server."""
    now = datetime.now(timezone.utc)
    timestamp = now.isoformat()
    print(f"[{timestamp}] Starting invoice purge (deleting invoices older than 24 hours)...")

    invoices = get_all_invoices()
    if not invoices:
        print(f"[{timestamp}] No invoices found")
        return 0

    deleted = 0
    failed = 0
    skipped = 0

    for invoice in invoices:
        invoice_id = invoice.get('id')
        if not invoice_id:
            continue

        created_time = parse_invoice_time(invoice)
        if not created_time:
            print(f"[WARN] Could not parse creation time for invoice {invoice_id}, skipping")
            skipped += 1
            continue

        age_seconds = (now - created_time).total_seconds()

        if age_seconds >= MAX_AGE_SECONDS:
            if delete_invoice(invoice_id):
                deleted += 1
                print(f"[INFO] Deleted invoice {invoice_id} (age: {age_seconds/3600:.1f} hours)")
            else:
                failed += 1
        else:
            skipped += 1

    print(f"[{timestamp}] Purge complete: {deleted} deleted, {skipped} skipped (too new), {failed} failed")
    return deleted


if __name__ == '__main__':
    purge_old_invoices()
