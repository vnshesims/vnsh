"""
VNSH eSIM Inventory API
Flask API for inventory-based eSIM storefront
"""

from flask import Flask, jsonify, request
from flask_cors import CORS
from database import (
    get_db, init_db, import_csv, get_inventory_options,
    get_countries, get_pricing, assign_esim, get_total_inventory,
    get_inventory_stats, delete_all_inventory,
    create_order, get_order, get_order_by_invoice, fulfill_order, cleanup_expired_orders,
    mark_order_viewed, purge_order_sensitive_data
)

# Privacy: Minimum inventory threshold to prevent identification
# Plans with fewer than this many eSIMs are hidden from customers
MIN_INVENTORY_THRESHOLD = 5
from pgp_utils import encrypt_message, validate_public_key
import secrets
import os
import hmac
import hashlib
import requests
import re
from pathlib import Path

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
BTCPAY_WEBHOOK_SECRET = os.environ.get('BTCPAY_WEBHOOK_SECRET', '')
BTCPAY_ONION_URL = os.environ.get('BTCPAY_ONION_URL', 'http://4yl2utzotn5uuoy6exiyr3gk2bt4ohnzmmb42ms7hvm57tp5et36ggad.onion')

app = Flask(__name__)
CORS(app)

@app.route('/api/health', methods=['GET'])
def health():
    """Health check endpoint."""
    return jsonify({"status": "ok"})


@app.route('/api/version', methods=['GET'])
def version():
    """Get current git commit hash."""
    try:
        with open('/app/COMMIT', 'r') as f:
            commit = f.read().strip()
    except:
        commit = "unknown"
    return jsonify({"commit": commit})

@app.route('/api/countries', methods=['GET'])
def countries():
    """Get list of countries with available inventory."""
    country_list = get_countries()
    # Filter out countries below minimum threshold and hide exact counts
    filtered = []
    for c in country_list:
        if c['total_inventory'] >= MIN_INVENTORY_THRESHOLD:
            filtered.append({
                "code": c['country'],
                "name": c['country'],
                "inventory": "In Stock"  # Don't expose exact count
            })
    return jsonify({"countries": filtered})

@app.route('/api/pricing', methods=['GET'])
def pricing():
    """
    Get pricing/plans for a country.
    Query params:
        - country: Country name (optional, returns all if not specified)
    """
    country = request.args.get('country', None)
    plans = get_pricing(country)

    # Format for frontend compatibility
    # Filter out plans below minimum threshold to prevent identification
    formatted_plans = []
    for p in plans:
        if p['inventory'] < MIN_INVENTORY_THRESHOLD:
            continue  # Hide low-inventory plans for privacy
        formatted_plans.append({
            "plan_id": f"{p['country']}_{p['duration_days']}_{p['data_gb']}_{p['price_usd']}",
            "plan_name": p['plan_name'],
            "duration_days": p['duration_days'],
            "data_gb": p['data_gb'],
            "price_usd": p['price_usd'],
            "inventory": "In Stock",  # Don't expose exact count
            "country": p['country'],
            "featured": p['duration_days'] == 30  # 30-day plans featured by default
        })

    return jsonify({
        "country": country or "all",
        "plans": formatted_plans
    })

@app.route('/api/inventory', methods=['GET'])
def inventory():
    """Get all inventory options with counts."""
    options = get_inventory_options()
    total = get_total_inventory()
    return jsonify({
        "total": total,
        "options": options
    })

@app.route('/api/stats', methods=['GET'])
def stats():
    """Get inventory statistics."""
    return jsonify(get_inventory_stats())

# Admin endpoints

@app.route('/api/admin/import', methods=['POST'])
def admin_import():
    """
    Import eSIMs from uploaded CSV.
    Expects multipart form with 'file' field.
    CSV format: lpa,country,days,price
    """
    if 'file' not in request.files:
        return jsonify({"error": "No file provided"}), 400

    file = request.files['file']
    if file.filename == '':
        return jsonify({"error": "No file selected"}), 400

    # Save temporarily and import
    temp_path = '/tmp/esim_import.csv'
    file.save(temp_path)

    try:
        imported, skipped, errors = import_csv(temp_path)
        return jsonify({
            "success": True,
            "imported": imported,
            "skipped": skipped,
            "errors": errors[:20] if len(errors) > 20 else errors,  # Limit errors shown
            "total_errors": len(errors)
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 500
    finally:
        if os.path.exists(temp_path):
            os.remove(temp_path)

@app.route('/api/admin/import-path', methods=['POST'])
def admin_import_path():
    """
    Import eSIMs from CSV file path on server.
    Body JSON: {"path": "/path/to/file.csv"}
    """
    data = request.get_json()
    if not data or 'path' not in data:
        return jsonify({"error": "path required"}), 400

    csv_path = data['path']
    if not os.path.exists(csv_path):
        return jsonify({"error": f"File not found: {csv_path}"}), 404

    try:
        imported, skipped, errors = import_csv(csv_path)
        return jsonify({
            "success": True,
            "imported": imported,
            "skipped": skipped,
            "errors": errors[:20] if len(errors) > 20 else errors,
            "total_errors": len(errors)
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/api/admin/clear', methods=['POST'])
def admin_clear():
    """Clear all inventory (use before reimporting)."""
    deleted = delete_all_inventory()
    return jsonify({
        "success": True,
        "deleted": deleted
    })

@app.route('/api/admin/assign', methods=['POST'])
def admin_assign():
    """
    Manually assign an eSIM (for testing).
    Body JSON: {"country": "...", "days": 7, "price": 15.00}
    """
    data = request.get_json()
    if not data:
        return jsonify({"error": "JSON body required"}), 400

    required = ['country', 'days', 'price']
    if not all(k in data for k in required):
        return jsonify({"error": f"Required fields: {required}"}), 400

    lpa = assign_esim(data['country'], data['days'], data['price'])
    if lpa:
        return jsonify({"success": True, "lpa": lpa})
    else:
        return jsonify({"success": False, "error": "No inventory available"}), 404


# Invoice creation endpoint

@app.route('/api/invoice', methods=['POST'])
def create_invoice():
    """
    Create a BTCPay invoice for eSIM purchase.

    Body JSON: {
        "plan_id": "...",
        "country": "...",
        "days": 7,
        "price": 15.00,
        "payment_method": "BTC" or "XMR",
        "pgp_public_key": "-----BEGIN PGP..." (optional)
    }
    """
    data = request.get_json()
    if not data:
        return jsonify({"error": "JSON body required"}), 400

    required = ['country', 'days', 'price', 'payment_method']
    if not all(k in data for k in required):
        return jsonify({"error": f"Required fields: {required}"}), 400

    country = data['country']
    days = int(data['days'])
    price = float(data['price'])
    payment_method = data['payment_method'].upper()
    pgp_public_key = data.get('pgp_public_key', '').strip() or None

    # Validate PGP key format if provided
    if pgp_public_key:
        if not pgp_public_key.startswith('-----BEGIN PGP PUBLIC KEY BLOCK-----'):
            return jsonify({"error": "Invalid PGP public key format"}), 400

    if payment_method not in ['BTC', 'XMR']:
        return jsonify({"error": "Invalid payment method. Use BTC or XMR"}), 400

    # Check inventory availability (must be above privacy threshold)
    pricing = get_pricing(country)
    matching_plan = None
    for p in pricing:
        if p['duration_days'] == days and float(p['price_usd']) == price:
            matching_plan = p
            break

    if not matching_plan or matching_plan['inventory'] < MIN_INVENTORY_THRESHOLD:
        return jsonify({"error": "Selected plan is out of stock"}), 400

    # Build item description
    item_desc = f"{country}-{days}d"

    # Generate secure order token
    order_token = secrets.token_urlsafe(24)

    # Create BTCPay invoice
    if not BTCPAY_API_KEY:
        return jsonify({"error": "BTCPay not configured"}), 500

    # Build redirect URL for after payment (goes to delivery page)
    storefront_onion = os.environ.get('STOREFRONT_ONION_URL', 'http://yftwmwb4oro3fbrljt4db24b2gbfmh4t4nxcq73z4blha2sx272aubyd.onion')
    redirect_url = f"{storefront_onion}/order/{order_token}"

    try:
        # BTCPay invoice payload
        invoice_data = {
            "amount": price,
            "currency": "USD",
            "metadata": {
                "itemDesc": item_desc,
                "price": price,
                "unlinkable": "1",
                "orderId": order_token
            },
            "checkout": {
                "speedPolicy": "HighSpeed",
                "redirectURL": redirect_url,
                "redirectAutomatically": True
            }
        }

        # Set payment method filter
        if payment_method == 'BTC':
            invoice_data["checkout"]["paymentMethods"] = ["BTC", "BTC-LightningNetwork"]
        elif payment_method == 'XMR':
            invoice_data["checkout"]["paymentMethods"] = ["XMR"]

        response = requests.post(
            f"{BTCPAY_URL}/api/v1/stores/{BTCPAY_STORE_ID}/invoices",
            headers={
                "Authorization": f"token {BTCPAY_API_KEY}",
                "Content-Type": "application/json"
            },
            json=invoice_data,
            timeout=15
        )

        if response.status_code not in (200, 201):
            # Check for specific errors
            if "wallet not available" in response.text.lower() or "node not available" in response.text.lower():
                return jsonify({"error": f"{payment_method} payments temporarily unavailable"}), 503
            return jsonify({"error": "Failed to create invoice"}), 500

        invoice = response.json()
        invoice_id = invoice.get('id', '')
        checkout_link = invoice.get('checkoutLink', '')

        # Replace internal URL with onion URL for customer-facing link
        if checkout_link and BTCPAY_ONION_URL:
            checkout_link = f"{BTCPAY_ONION_URL}/i/{invoice_id}"

        # Create order record linking invoice to order token
        create_order(order_token, invoice_id, country, days, price, pgp_public_key)

        # Fetch payment method details for inline display
        payment_address = None
        payment_amount = None
        payment_link = None

        try:
            pm_response = requests.get(
                f"{BTCPAY_URL}/api/v1/stores/{BTCPAY_STORE_ID}/invoices/{invoice_id}/payment-methods",
                headers={"Authorization": f"token {BTCPAY_API_KEY}"},
                timeout=10
            )
            if pm_response.status_code == 200:
                payment_methods = pm_response.json()
                # Find the relevant payment method
                for pm in payment_methods:
                    pm_id = pm.get('paymentMethodId', '')
                    if payment_method == 'BTC' and pm_id in ['BTC', 'BTC-CHAIN']:
                        payment_address = pm.get('destination', '')
                        payment_amount = pm.get('due', '')
                        payment_link = f"bitcoin:{payment_address}?amount={payment_amount}"
                        break
                    elif payment_method == 'BTC' and 'LightningNetwork' in pm_id:
                        # Lightning invoice
                        payment_address = pm.get('destination', '')
                        payment_amount = pm.get('due', '')
                        payment_link = payment_address  # Lightning is already a link
                        break
                    elif payment_method == 'XMR' and pm_id in ['XMR', 'XMR-CHAIN']:
                        payment_address = pm.get('destination', '')
                        payment_amount = pm.get('due', '')
                        payment_link = f"monero:{payment_address}?tx_amount={payment_amount}"
                        break
        except Exception:
            pass  # Silently fail - no logging for privacy

        return jsonify({
            "success": True,
            "invoice_id": invoice_id,
            "checkout_url": checkout_link,
            "order_id": order_token,
            "payment_method": payment_method,
            "payment_address": payment_address,
            "payment_amount": payment_amount,
            "payment_link": payment_link,
            "price_usd": price
        })

    except requests.exceptions.Timeout:
        return jsonify({"error": "Payment server timeout"}), 504
    except Exception:
        return jsonify({"error": "Failed to create invoice"}), 500


# BTCPay webhook handler

def verify_btcpay_signature(payload, signature):
    """Verify BTCPay webhook signature."""
    if not BTCPAY_WEBHOOK_SECRET:
        return True  # Skip verification if no secret configured
    expected = hmac.new(
        BTCPAY_WEBHOOK_SECRET.encode(),
        payload,
        hashlib.sha256
    ).hexdigest()
    return hmac.compare_digest(f"sha256={expected}", signature)


def delete_btcpay_invoice(invoice_id):
    """Delete invoice from BTCPay Server to leave no trace."""
    if not BTCPAY_API_KEY:
        return False

    try:
        response = requests.delete(
            f"{BTCPAY_URL}/api/v1/stores/{BTCPAY_STORE_ID}/invoices/{invoice_id}",
            headers={"Authorization": f"token {BTCPAY_API_KEY}"},
            timeout=10
        )
        return response.status_code in (200, 204)
    except Exception:
        return False


def parse_item_desc(item_desc):
    """
    Parse itemDesc like 'US-7d' or 'Germany-30d' into country and days.
    Returns (country, days) or (None, None) if parsing fails.
    """
    match = re.match(r'^(.+)-(\d+)d$', item_desc)
    if match:
        return match.group(1), int(match.group(2))
    return None, None


@app.route('/api/webhook/btcpay', methods=['POST'])
def btcpay_webhook():
    """
    Handle BTCPay Server webhook for payment confirmations.

    When payment is confirmed:
    1. Parse the order details from itemDesc
    2. Assign a random eSIM from inventory
    3. Delete the invoice from BTCPay (if unlinkable)
    4. Return the LPA code for delivery

    The LPA is returned in the response but NOT stored with any
    payment reference when unlinkable=1, making it impossible
    to associate payment with the specific eSIM.
    """
    # Verify signature
    signature = request.headers.get('BTCPay-Sig', '')
    if not verify_btcpay_signature(request.data, signature):
        return jsonify({"error": "Invalid signature"}), 401

    data = request.get_json()
    if not data:
        return jsonify({"error": "No data"}), 400

    event_type = data.get('type', '')

    # Only process settled invoices (payment confirmed)
    if event_type != 'InvoiceSettled':
        return jsonify({"status": "ignored", "reason": f"Event type: {event_type}"}), 200

    invoice_id = data.get('invoiceId', '')
    metadata = data.get('metadata', {})

    # Get order details
    item_desc = metadata.get('itemDesc', '')
    price = metadata.get('price')
    unlinkable = metadata.get('unlinkable', '1')  # Default to unlinkable

    # Parse country and duration from itemDesc (e.g., "US-7d")
    country, days = parse_item_desc(item_desc)

    if not country or not days or not price:
        return jsonify({"error": "Invalid order data"}), 400

    try:
        price = float(price)
    except (ValueError, TypeError):
        return jsonify({"error": "Invalid price"}), 400

    # Get the order linked to this invoice
    order = get_order_by_invoice(invoice_id)
    if not order:
        return jsonify({"error": "Order not found"}), 404

    # Assign a random eSIM from inventory
    lpa = assign_esim(country, days, price)

    if not lpa:
        return jsonify({"error": "No inventory available"}), 500

    # Fulfill the order with the LPA
    fulfill_order(invoice_id, lpa)

    # Return success - customer will see LPA on delivery page
    return jsonify({
        "status": "success"
    })


@app.route('/api/lookup', methods=['GET'])
def lookup_order():
    """
    Lookup order by invoice ID.
    Returns the order_id token if found.
    """
    invoice_id = request.args.get('invoice_id', '').strip()
    if not invoice_id:
        return jsonify({"error": "invoice_id required"}), 400

    order = get_order_by_invoice(invoice_id)
    if not order:
        return jsonify({"error": "Order not found"}), 404

    return jsonify({
        "order_id": order['order_id'],
        "status": order['status']
    })


@app.route('/api/order/<order_id>', methods=['GET'])
def get_order_status(order_id):
    """
    Get order status and LPA if fulfilled.
    Customer polls this endpoint after payment.
    """
    order = get_order(order_id)

    if not order:
        return jsonify({"error": "Order not found"}), 404

    # Clean up expired orders periodically
    cleanup_expired_orders()

    if order['status'] == 'fulfilled' and order.get('lpa'):
        lpa = order['lpa']
        encrypted = False

        # Encrypt LPA if customer provided a PGP key
        pgp_key = order.get('pgp_public_key')
        if pgp_key:
            try:
                lpa = encrypt_message(lpa, pgp_key)
                encrypted = True
            except Exception:
                # If encryption fails, still return the raw LPA
                pass

        # Mark as viewed and purge sensitive data immediately
        mark_order_viewed(order_id)
        purge_order_sensitive_data(order_id)

        return jsonify({
            "status": "fulfilled",
            "lpa": lpa,
            "encrypted": encrypted
        })
    elif order['status'] == 'pending':
        return jsonify({
            "status": "pending"
        })
    else:
        return jsonify({
            "status": order['status']
        })


if __name__ == "__main__":
    # Initialize database on startup
    init_db()

    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=False)
