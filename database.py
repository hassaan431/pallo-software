import re
import sqlite3
from pathlib import Path

from werkzeug.security import generate_password_hash

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
                amount REAL DEFAULT 0
            );

            CREATE TABLE IF NOT EXISTS product_variants (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                product_id INTEGER REFERENCES products(id),
                size TEXT,
                flavor TEXT,
                price_adjustment REAL DEFAULT 0
            );
            """
        )
        
        # Safely add amount_paid column to sales table
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
            "INSERT INTO users (username, password_hash) VALUES (?, ?)",
            ("admin", generate_password_hash("admin123")),
        )
    for name in _DEFAULT_CATEGORY_NAMES:
        cur.execute("INSERT OR IGNORE INTO categories (name) VALUES (?)", (name,))
    conn.commit()


def get_next_invoice_number():
    conn = get_connection()
    try:
        row = conn.execute(
            "SELECT MAX(invoice_number) AS max_invoice FROM sales"
        ).fetchone()

        max_invoice = None if not row else row["max_invoice"]
        if not max_invoice:
            return "AK-000001"

        inv = str(max_invoice).strip()
        match = re.match(r"(?i)^AK-(\d+)$", inv)
        if match:
            next_num = int(match.group(1)) + 1
            return f"AK-{next_num:06d}"

        # Fallback: extract numeric parts from all AK-* invoice numbers
        rows = conn.execute(
            "SELECT invoice_number FROM sales WHERE invoice_number LIKE 'AK-%'"
        ).fetchall()
        nums = []
        for r in rows:
            m = re.match(r"(?i)^AK-(\d+)$", str(r["invoice_number"]).strip())
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
            "SELECT id, username, password_hash FROM users WHERE id = ?",
            (user_id,),
        )
        return cur.fetchone()
    finally:
        conn.close()


def get_user_by_username(username: str):
    conn = get_connection()
    try:
        cur = conn.execute(
            "SELECT id, username, password_hash FROM users WHERE username = ?",
            (username,),
        )
        return cur.fetchone()
    finally:
        conn.close()
