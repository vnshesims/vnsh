"""
VNSH eSIM Inventory Database
SQLite-based inventory management with LPA codes
"""

import sqlite3
import csv
from datetime import datetime
from pathlib import Path

DB_PATH = Path(__file__).parent / "vnsh.db"

def get_db():
    """Get database connection with row factory."""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    """Initialize database schema."""
    conn = get_db()
    cursor = conn.cursor()

    # eSIM inventory table - each row is one eSIM
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS esim_inventory (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            lpa TEXT UNIQUE NOT NULL,
            country TEXT NOT NULL,
            days INTEGER NOT NULL,
            data_gb INTEGER NOT NULL DEFAULT 1,
            price_usd REAL NOT NULL,
            status TEXT DEFAULT 'available',
            assigned_at TIMESTAMP,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    # Add data_gb column if it doesn't exist (for existing databases)
    try:
        cursor.execute("ALTER TABLE esim_inventory ADD COLUMN data_gb INTEGER NOT NULL DEFAULT 1")
    except sqlite3.OperationalError:
        pass  # Column already exists

    # Index for fast lookups
    cursor.execute("""
        CREATE INDEX IF NOT EXISTS idx_esim_status ON esim_inventory(status)
    """)
    cursor.execute("""
        CREATE INDEX IF NOT EXISTS idx_esim_country_days ON esim_inventory(country, days, status)
    """)

    # Orders table - for tracking (purged after 24h)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS orders (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            order_id TEXT UNIQUE NOT NULL,
            esim_id INTEGER,
            price_usd REAL NOT NULL,
            status TEXT DEFAULT 'pending',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            expires_at TIMESTAMP,
            FOREIGN KEY (esim_id) REFERENCES esim_inventory(id)
        )
    """)

    conn.commit()
    conn.close()

def import_csv(csv_path):
    """
    Import eSIMs from CSV file.
    CSV format: lpa,country,days,price
    Returns tuple of (imported_count, skipped_count, errors)
    """
    conn = get_db()
    cursor = conn.cursor()

    imported = 0
    skipped = 0
    errors = []

    with open(csv_path, 'r', newline='', encoding='utf-8') as f:
        reader = csv.DictReader(f)

        for row_num, row in enumerate(reader, start=2):  # Start at 2 (header is row 1)
            try:
                lpa = row.get('lpa', '').strip()
                country = row.get('country', '').strip()
                days = row.get('days', '').strip()
                price = row.get('price', '').strip()

                # Validate required fields
                if not lpa:
                    errors.append(f"Row {row_num}: Missing LPA")
                    skipped += 1
                    continue
                if not country:
                    errors.append(f"Row {row_num}: Missing country")
                    skipped += 1
                    continue
                if not days:
                    errors.append(f"Row {row_num}: Missing days")
                    skipped += 1
                    continue
                if not price:
                    errors.append(f"Row {row_num}: Missing price")
                    skipped += 1
                    continue

                # Convert types
                try:
                    days = int(days)
                except ValueError:
                    errors.append(f"Row {row_num}: Invalid days value '{days}'")
                    skipped += 1
                    continue

                try:
                    price = float(price)
                except ValueError:
                    errors.append(f"Row {row_num}: Invalid price value '{price}'")
                    skipped += 1
                    continue

                # Insert eSIM
                cursor.execute("""
                    INSERT INTO esim_inventory (lpa, country, days, price_usd, status)
                    VALUES (?, ?, ?, ?, 'available')
                """, (lpa, country, days, price))
                imported += 1

            except sqlite3.IntegrityError:
                errors.append(f"Row {row_num}: Duplicate LPA '{lpa}'")
                skipped += 1
            except Exception as e:
                errors.append(f"Row {row_num}: {str(e)}")
                skipped += 1

    conn.commit()
    conn.close()

    return imported, skipped, errors

def get_inventory_options():
    """
    Get available options for the storefront.
    Returns unique country/days/data_gb/price combinations with inventory count.
    """
    conn = get_db()
    cursor = conn.cursor()

    cursor.execute("""
        SELECT
            country,
            days,
            data_gb,
            price_usd,
            COUNT(*) as inventory
        FROM esim_inventory
        WHERE status = 'available'
        GROUP BY country, days, data_gb, price_usd
        ORDER BY country, days
    """)

    results = [dict(row) for row in cursor.fetchall()]
    conn.close()
    return results

def get_countries():
    """Get list of countries with available inventory."""
    conn = get_db()
    cursor = conn.cursor()

    cursor.execute("""
        SELECT DISTINCT country, COUNT(*) as total_inventory
        FROM esim_inventory
        WHERE status = 'available'
        GROUP BY country
        ORDER BY country
    """)

    results = [dict(row) for row in cursor.fetchall()]
    conn.close()
    return results

def get_plans_for_country(country):
    """Get available plans (days/price combinations) for a specific country."""
    conn = get_db()
    cursor = conn.cursor()

    cursor.execute("""
        SELECT
            days,
            price_usd,
            COUNT(*) as inventory
        FROM esim_inventory
        WHERE status = 'available' AND country = ?
        GROUP BY days, price_usd
        ORDER BY days
    """)

    results = [dict(row) for row in cursor.fetchall()]
    conn.close()
    return results

def get_pricing(country=None):
    """
    Get pricing/plans for display.
    Returns plans grouped by country with inventory counts.
    """
    conn = get_db()
    cursor = conn.cursor()

    if country:
        cursor.execute("""
            SELECT
                country,
                days as duration_days,
                data_gb,
                price_usd,
                COUNT(*) as inventory,
                days || ' Day' || CASE WHEN days > 1 THEN 's' ELSE '' END || ' - ' || data_gb || 'GB' as plan_name
            FROM esim_inventory
            WHERE status = 'available' AND country = ?
            GROUP BY country, days, data_gb, price_usd
            ORDER BY days
        """, (country,))
    else:
        cursor.execute("""
            SELECT
                country,
                days as duration_days,
                data_gb,
                price_usd,
                COUNT(*) as inventory,
                days || ' Day' || CASE WHEN days > 1 THEN 's' ELSE '' END || ' - ' || data_gb || 'GB' as plan_name
            FROM esim_inventory
            WHERE status = 'available'
            GROUP BY country, days, data_gb, price_usd
            ORDER BY country, days
        """)

    results = [dict(row) for row in cursor.fetchall()]
    conn.close()
    return results

def assign_esim(country, days, price_usd):
    """
    Assign an available eSIM to a purchase.
    Returns the LPA code or None if no inventory.
    """
    conn = get_db()
    cursor = conn.cursor()

    # Select a random available eSIM matching criteria
    cursor.execute("""
        SELECT id, lpa FROM esim_inventory
        WHERE status = 'available'
          AND country = ?
          AND days = ?
          AND price_usd = ?
        ORDER BY RANDOM()
        LIMIT 1
    """, (country, days, price_usd))

    row = cursor.fetchone()

    if row:
        # Mark as assigned
        cursor.execute("""
            UPDATE esim_inventory
            SET status = 'assigned', assigned_at = CURRENT_TIMESTAMP
            WHERE id = ?
        """, (row['id'],))
        conn.commit()
        conn.close()
        return row['lpa']

    conn.close()
    return None

def get_total_inventory():
    """Get total available inventory count."""
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT COUNT(*) as total FROM esim_inventory WHERE status = 'available'")
    result = cursor.fetchone()['total']
    conn.close()
    return result

def get_inventory_stats():
    """Get detailed inventory statistics."""
    conn = get_db()
    cursor = conn.cursor()

    cursor.execute("""
        SELECT
            status,
            COUNT(*) as count
        FROM esim_inventory
        GROUP BY status
    """)

    stats = {row['status']: row['count'] for row in cursor.fetchall()}
    conn.close()
    return stats

def delete_all_inventory():
    """Delete all inventory (for reimporting)."""
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM esim_inventory")
    deleted = cursor.rowcount
    conn.commit()
    conn.close()
    return deleted


# Order management functions

def create_order(order_id, invoice_id, country, days, price_usd, pgp_public_key=None):
    """
    Create a pending order when invoice is created.
    order_id is a secure random token for the customer.
    invoice_id is the BTCPay invoice ID.
    pgp_public_key is optional - if provided, LPA will be encrypted on delivery.
    """
    conn = get_db()
    cursor = conn.cursor()

    # Add invoice_id and country/days columns if they don't exist
    try:
        cursor.execute("ALTER TABLE orders ADD COLUMN invoice_id TEXT")
    except sqlite3.OperationalError:
        pass
    try:
        cursor.execute("ALTER TABLE orders ADD COLUMN country TEXT")
    except sqlite3.OperationalError:
        pass
    try:
        cursor.execute("ALTER TABLE orders ADD COLUMN days INTEGER")
    except sqlite3.OperationalError:
        pass
    try:
        cursor.execute("ALTER TABLE orders ADD COLUMN lpa TEXT")
    except sqlite3.OperationalError:
        pass
    try:
        cursor.execute("ALTER TABLE orders ADD COLUMN pgp_public_key TEXT")
    except sqlite3.OperationalError:
        pass

    cursor.execute("""
        INSERT INTO orders (order_id, invoice_id, country, days, price_usd, pgp_public_key, status, expires_at)
        VALUES (?, ?, ?, ?, ?, ?, 'pending', datetime('now', '+1 hour'))
    """, (order_id, invoice_id, country, days, price_usd, pgp_public_key))

    conn.commit()
    conn.close()
    return order_id


def get_order_by_invoice(invoice_id):
    """Get order by BTCPay invoice ID."""
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM orders WHERE invoice_id = ?", (invoice_id,))
    row = cursor.fetchone()
    conn.close()
    return dict(row) if row else None


def get_order(order_id):
    """Get order by order_id (customer token)."""
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM orders WHERE order_id = ?", (order_id,))
    row = cursor.fetchone()
    conn.close()
    return dict(row) if row else None


def fulfill_order(invoice_id, lpa):
    """Mark order as fulfilled, store the LPA, and generate destruction proof."""
    import hashlib
    from datetime import datetime

    conn = get_db()
    cursor = conn.cursor()

    # Add destruction_proof column if it doesn't exist
    try:
        cursor.execute("ALTER TABLE orders ADD COLUMN destruction_proof TEXT")
    except sqlite3.OperationalError:
        pass

    # Generate destruction proof: hash of invoice_id + lpa + timestamp
    timestamp = datetime.utcnow().isoformat()
    proof_data = f"{invoice_id}:{lpa}:{timestamp}"
    destruction_proof = hashlib.sha256(proof_data.encode()).hexdigest()

    cursor.execute("""
        UPDATE orders
        SET status = 'fulfilled', lpa = ?, destruction_proof = ?
        WHERE invoice_id = ?
    """, (lpa, destruction_proof, invoice_id))
    updated = cursor.rowcount

    # Delete the eSIM from inventory (it's been assigned and delivered)
    if updated > 0:
        cursor.execute("DELETE FROM esim_inventory WHERE lpa = ?", (lpa,))

    conn.commit()
    conn.close()
    return updated > 0


def mark_order_viewed(order_id):
    """Mark order as viewed (one-time display)."""
    conn = get_db()
    cursor = conn.cursor()

    # Add viewed column if it doesn't exist
    try:
        cursor.execute("ALTER TABLE orders ADD COLUMN viewed INTEGER DEFAULT 0")
    except sqlite3.OperationalError:
        pass

    cursor.execute("""
        UPDATE orders
        SET viewed = 1
        WHERE order_id = ? AND status = 'fulfilled'
    """, (order_id,))
    conn.commit()
    conn.close()


def is_order_viewed(order_id):
    """Check if order has already been viewed."""
    conn = get_db()
    cursor = conn.cursor()

    # Add viewed column if it doesn't exist
    try:
        cursor.execute("ALTER TABLE orders ADD COLUMN viewed INTEGER DEFAULT 0")
    except sqlite3.OperationalError:
        pass

    cursor.execute("SELECT viewed FROM orders WHERE order_id = ?", (order_id,))
    row = cursor.fetchone()
    conn.close()
    return row and row['viewed'] == 1


def cleanup_expired_orders():
    """Delete expired pending orders (privacy cleanup)."""
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("""
        DELETE FROM orders
        WHERE status = 'pending' AND expires_at < datetime('now')
    """)
    deleted = cursor.rowcount
    # Delete fulfilled orders after 1 hour (reduced from 24 for privacy)
    cursor.execute("""
        DELETE FROM orders
        WHERE status = 'fulfilled' AND created_at < datetime('now', '-1 hour')
    """)
    deleted += cursor.rowcount
    # Delete viewed orders after 10 minutes (customer already got their LPA)
    cursor.execute("""
        DELETE FROM orders
        WHERE status = 'fulfilled' AND viewed = 1 AND created_at < datetime('now', '-10 minutes')
    """)
    deleted += cursor.rowcount
    conn.commit()
    conn.close()
    return deleted


def purge_order_sensitive_data(order_id):
    """
    Purge sensitive data from order after customer views it.
    Keeps only minimal record for debugging, removes LPA and PGP key.
    """
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("""
        UPDATE orders
        SET lpa = NULL, pgp_public_key = NULL, invoice_id = NULL
        WHERE order_id = ? AND viewed = 1
    """, (order_id,))
    conn.commit()
    conn.close()


if __name__ == "__main__":
    init_db()

    print("\nInventory stats:")
    stats = get_inventory_stats()
    for status, count in stats.items():
        print(f"  {status}: {count}")

    print("\nAvailable options:")
    for opt in get_inventory_options():
        print(f"  {opt['country']} - {opt['days']} days @ ${opt['price_usd']} ({opt['inventory']} available)")

    print("\nCountries:")
    for c in get_countries():
        print(f"  {c['country']}: {c['total_inventory']} eSIMs")
