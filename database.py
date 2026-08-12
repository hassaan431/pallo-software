import re
import sqlite3
from pathlib import Path
import sys

from werkzeug.security import generate_password_hash

# Use executable directory when frozen (PyInstaller), else use script directory
if getattr(sys, 'frozen', False):
    DB_PATH = Path(sys.executable).resolve().parent / "database.db"
else:
    DB_PATH = Path(__file__).resolve().parent / "database.db"

_DEFAULT_CATEGORY_NAMES = (
    "Food",
    "Spices",
    "Beverages",
    "Dairy",
    "Dry Goods",
    "Other",
)


def get_connection():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def init_db():
    conn = get_connection()
    try:
        cur = conn.cursor()
        cur.executescript(
            """
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT UNIQUE NOT NULL,
                password_hash TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS customers (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                bill_address TEXT,
                ship_address TEXT,
                area TEXT,
                state TEXT,
                phone TEXT,
                email TEXT,
                terms TEXT DEFAULT 'Due on Receipt',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );

            CREATE TABLE IF NOT EXISTS categories (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT UNIQUE NOT NULL
            );

            CREATE TABLE IF NOT EXISTS brands (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT UNIQUE NOT NULL
            );

            CREATE TABLE IF NOT EXISTS products (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                category_id INTEGER REFERENCES categories(id),
                brand TEXT,
                unit TEXT DEFAULT 'Each',
                cost_price REAL DEFAULT 0,
                selling_price REAL DEFAULT 0,
                stock_quantity REAL DEFAULT 0,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );

            CREATE TABLE IF NOT EXISTS sales (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                invoice_number TEXT UNIQUE NOT NULL,
                customer_id INTEGER REFERENCES customers(id),
                invoice_date TEXT NOT NULL,
                due_date TEXT,
                terms TEXT,
                payment_type TEXT CHECK(payment_type IN ('cash','cheque','credit')) DEFAULT 'cash',
                discount_amount REAL DEFAULT 0,
                subtotal REAL DEFAULT 0,
                grand_total REAL DEFAULT 0,
                notes TEXT,
                status TEXT DEFAULT 'unpaid',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );

            CREATE TABLE IF NOT EXISTS sale_items (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                sale_id INTEGER REFERENCES sales(id),
                product_id INTEGER REFERENCES products(id),
                description TEXT,
                qty REAL DEFAULT 1,
                rate REAL DEFAULT 0,
                amount REAL DEFAULT 0,
                cost_price REAL DEFAULT 0
            );

            CREATE TABLE IF NOT EXISTS inventory_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                product_id INTEGER REFERENCES products(id),
                transaction_type TEXT NOT NULL,
                quantity_change REAL NOT NULL,
                previous_stock REAL NOT NULL,
                new_stock REAL NOT NULL,
                reference TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );

            CREATE TABLE IF NOT EXISTS suppliers (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                contact_name TEXT,
                phone TEXT,
                address TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );

            """
        )
        
        # Safely add supplier_id column to products table
        try:
            conn.execute("ALTER TABLE products ADD COLUMN supplier_id INTEGER REFERENCES suppliers(id)")
            conn.commit()
        except sqlite3.OperationalError:
            pass

        # Safely add supplier_id column to inventory_history table
        try:
            conn.execute("ALTER TABLE inventory_history ADD COLUMN supplier_id INTEGER REFERENCES suppliers(id)")
            conn.commit()
        except sqlite3.OperationalError:
            pass
        
        # Safely add brand column to products table
        try:
            conn.execute(
                "ALTER TABLE products ADD COLUMN brand TEXT"
            )
        except sqlite3.OperationalError:
            pass

        # Safely add role column to users table
        try:
            conn.execute(
                "ALTER TABLE users ADD COLUMN role TEXT DEFAULT 'admin'"
            )
        except sqlite3.OperationalError:
            pass
            
        try:
            conn.execute(
                "ALTER TABLE users ADD COLUMN is_active INTEGER DEFAULT 1"
            )
        except sqlite3.OperationalError:
            pass
            
        # Safely add image_url column to products table
        try:
            conn.execute(
                "ALTER TABLE products ADD COLUMN image_url TEXT"
            )
        except sqlite3.OperationalError:
            pass
            
        # Safely add is_public column to products table
        try:
            conn.execute(
                "ALTER TABLE products ADD COLUMN is_public INTEGER DEFAULT 1"
            )
        except sqlite3.OperationalError:
            pass

        try:
            conn.execute(
                "ALTER TABLE sale_items ADD COLUMN print_dual_units INTEGER DEFAULT 0"
            )
            conn.commit()
        except sqlite3.OperationalError:
            pass
            
        # Safely add salesman_id column to sales table
        try:
            conn.execute(
                "ALTER TABLE sales ADD COLUMN salesman_id INTEGER REFERENCES users(id)"
            )
        except sqlite3.OperationalError:
            pass

        # Safely add cost_price column to sale_items table if it doesn't exist
        try:
            conn.execute(
                "ALTER TABLE sale_items ADD COLUMN cost_price REAL DEFAULT 0"
            )
            # Update existing sale_items with current cost_price from products
            conn.execute(
                """
                UPDATE sale_items 
                SET cost_price = COALESCE((SELECT cost_price FROM products WHERE id = sale_items.product_id), 0)
                WHERE cost_price = 0
                """
            )
        except sqlite3.OperationalError:
            pass

        try:
            conn.execute(
                "ALTER TABLE sales ADD COLUMN "
                "amount_paid REAL DEFAULT 0"
            )
            conn.commit()
        except Exception:
            pass  # Column already exists

        # Safely add remaining_amount column to sales
        try:
            conn.execute(
                "ALTER TABLE sales ADD COLUMN "
                "remaining_amount REAL DEFAULT 0"
            )
            conn.commit()
        except Exception:
            pass  # Column already exists

        # Update existing cash/cheque sales
        try:
            conn.execute("""
                UPDATE sales 
                SET amount_paid = grand_total,
                    remaining_amount = 0
                WHERE payment_type IN ('cash', 'cheque')
                AND (amount_paid = 0 OR amount_paid IS NULL)
            """)
            conn.execute("""
                UPDATE sales 
                SET amount_paid = 0,
                    remaining_amount = grand_total
                WHERE payment_type = 'credit'
                AND (remaining_amount = 0 
                     OR remaining_amount IS NULL)
            """)
            conn.commit()
        except Exception:
            pass
        
        # Ensure that the statuses reflect correct paid/partial/unpaid states for all sales
        try:
            conn.execute("""
                UPDATE sales 
                SET status = CASE 
                    WHEN remaining_amount <= 0 THEN 'paid'
                    WHEN amount_paid > 0 THEN 'partial'
                    ELSE 'unpaid'
                END
            """)
            conn.commit()
        except Exception:
            pass
        
        conn.commit()
        _migrate_database(conn)
        _seed_default_data(conn)
    finally:
        conn.close()


def _migrate_database(conn):
    """Add state column to customers table if it doesn't exist"""
    cur = conn.cursor()
    # Check if state column exists in customers table
    cur.execute("PRAGMA table_info(customers)")
    columns = [row[1] for row in cur.fetchall()]
    if 'state' not in columns:
        cur.execute("ALTER TABLE customers ADD COLUMN state TEXT")
        conn.commit()


def _seed_default_data(conn):
    cur = conn.cursor()
    cur.execute("SELECT 1 FROM users WHERE username = ?", ("admin",))
    if cur.fetchone() is None:
        cur.execute(
            "INSERT INTO users (username, password_hash, role) VALUES (?, ?, ?)",
            ("admin", generate_password_hash("admin123", method="pbkdf2:sha256"), "admin"),
        )
        print("Inserted default admin user")

    # Seed default salesman if not exists
    cur.execute("SELECT id FROM users WHERE username = 'salesman'")
    if cur.fetchone() is None:
        cur.execute(
            "INSERT INTO users (username, password_hash, role) VALUES (?, ?, ?)",
            ("salesman", generate_password_hash("password", method="pbkdf2:sha256"), "salesman"),
        )
        
    for name in _DEFAULT_CATEGORY_NAMES:
        cur.execute("INSERT OR IGNORE INTO categories (name) VALUES (?)", (name,))
    conn.commit()


def get_next_invoice_number():
    conn = get_connection()
    try:
        rows = conn.execute(
            "SELECT invoice_number FROM sales WHERE invoice_number LIKE 'AK-%' OR invoice_number LIKE 'Q-%'"
        ).fetchall()
        nums = []
        for r in rows:
            inv = str(r["invoice_number"]).strip()
            m = re.search(r"(\d+)$", inv)
            if m:
                nums.append(int(m.group(1)))

        if not nums:
            return "AK-000001"
        return f"AK-{(max(nums) + 1):06d}"
    finally:
        conn.close()


def get_user_by_id(user_id: int):
    conn = get_connection()
    try:
        cur = conn.execute(
            "SELECT id, username, role, is_active FROM users WHERE id = ?", (user_id,)
        )
        return cur.fetchone()
    finally:
        conn.close()


def get_user_by_username(username: str):
    conn = get_connection()
    try:
        cur = conn.execute(
            "SELECT id, username, password_hash, role, is_active FROM users WHERE username = ?",
            (username,),
        )
        return cur.fetchone()
    finally:
        conn.close()


def get_public_products():
    conn = get_connection()
    try:
        cur = conn.execute(
            """
            SELECT p.id, p.name, p.brand, p.image_url, c.name as category_name
            FROM products p
            LEFT JOIN categories c ON p.category_id = c.id
            WHERE p.is_public = 1
            ORDER BY p.name COLLATE NOCASE
            """
        )
        return [dict(row) for row in cur.fetchall()]
    finally:
        conn.close()


import string

def get_brand_logo_filename(brand_name: str):
    if not brand_name:
        return None
    brands_dir = DB_PATH.parent / "static" / "logos" / "brands"
    if not brands_dir.exists():
        return None
    
    # Fast exact match check
    exact_path = brands_dir / f"{brand_name}.png"
    if exact_path.exists():
        return f"{brand_name}.png"
        
    def normalize(s):
        if not s: return ""
        return s.strip().lower().replace(" ", "").translate(str.maketrans('', '', string.punctuation))

    b = normalize(brand_name)
    if not b:
        return None
        
    # Iterate through available files and use robust substring matching
    for f in brands_dir.glob("*.png"):
        f_norm = normalize(f.stem)
        if not f_norm: continue
        if b == f_norm or f_norm in b or b in f_norm:
            return f.name
            
    return None


