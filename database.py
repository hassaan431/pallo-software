import logging
import os
import re
import sqlite3
import sys
import threading
from contextlib import contextmanager
from pathlib import Path

from dotenv import load_dotenv
import psycopg2
from psycopg2.extras import RealDictCursor
from psycopg2.pool import PoolError, ThreadedConnectionPool
from werkzeug.security import generate_password_hash

# Load environment variables from .env file if present
load_dotenv()

logger = logging.getLogger("pallo.database")

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

# Global PostgreSQL Threaded Connection Pool and sync lock
_pg_pool = None
_pg_pool_lock = threading.Lock()


def normalize_database_url(url: str | None) -> str:
    """Normalize DATABASE_URL for psycopg2 compatibility (e.g. postgres:// to postgresql://)."""
    if not url:
        return ""
    url = url.strip()
    if url.startswith("postgres://"):
        url = "postgresql://" + url[len("postgres://"):]
    return url


def get_database_url() -> str:
    """Return normalized DATABASE_URL from environment."""
    return normalize_database_url(os.environ.get("DATABASE_URL", ""))


def is_postgres_configured() -> bool:
    """Check if a PostgreSQL DATABASE_URL is set in environment."""
    return bool(get_database_url())


def get_pool():
    """Lazily initialize and return the global ThreadedConnectionPool."""
    global _pg_pool
    if _pg_pool is not None:
        return _pg_pool

    db_url = get_database_url()
    if not db_url:
        return None

    with _pg_pool_lock:
        if _pg_pool is None:
            minconn = int(os.environ.get("DB_POOL_MIN", 1))
            maxconn = int(os.environ.get("DB_POOL_MAX", 20))
            logger.info("Initializing PostgreSQL ThreadedConnectionPool (min=%d, max=%d)", minconn, maxconn)
            _pg_pool = ThreadedConnectionPool(minconn=minconn, maxconn=maxconn, dsn=db_url)
    return _pg_pool


def close_pool():
    """Cleanly close all connections in the PostgreSQL connection pool."""
    global _pg_pool
    with _pg_pool_lock:
        if _pg_pool is not None:
            _pg_pool.closeall()
            _pg_pool = None
            logger.info("PostgreSQL ThreadedConnectionPool closed.")


def get_pool_status() -> dict:
    """Inspect current connection pool status."""
    if not is_postgres_configured():
        return {"configured": False, "engine": "sqlite"}
    pool = get_pool()
    if pool is None:
        return {"configured": True, "status": "uninitialized"}
    return {
        "configured": True,
        "engine": "postgresql",
        "minconn": pool.minconn,
        "maxconn": pool.maxconn,
        "closed": pool.closed,
    }


class PooledConnectionWrapper:
    """
    Transparent proxy wrapper around a psycopg2 connection checked out from ThreadedConnectionPool.
    - Intercepts .close() to return the connection to the pool rather than terminating the socket.
    - Defaults .cursor() to use RealDictCursor for dict-like column access matching sqlite3.Row.
    - Performs safety rollback on uncommitted transactions before pool return to prevent cross-request leakage.
    """

class PooledCursorWrapper:
    """Cursor wrapper that adapts '?' parameter placeholders to '%s' for PostgreSQL execution."""

    def __init__(self, raw_cursor):
        self._cur = raw_cursor

    def execute(self, query, params=None):
        if "?" in query:
            query = query.replace("?", "%s")
        if params is None:
            return self._cur.execute(query)
        if isinstance(params, list):
            params = tuple(params)
        return self._cur.execute(query, params)

    def executemany(self, query, params_seq):
        if "?" in query:
            query = query.replace("?", "%s")
        return self._cur.executemany(query, params_seq)

    def __iter__(self):
        return iter(self._cur)

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self._cur.close()

    def __getattr__(self, name):
        return getattr(self._cur, name)


class PooledConnectionWrapper:
    """
    A lightweight thread-safe wrapper around a psycopg2 pooled connection that:
    - Overrides .close() to return the connection back to the ThreadedConnectionPool instead of terminating it.
    - Defaults .cursor() to use RealDictCursor for dict-like column access matching sqlite3.Row.
    - Performs safety rollback on uncommitted transactions before pool return to prevent cross-request leakage.
    - Provides .execute() and adapts '?' parameter placeholders to '%s' for transparent cross-database queries.
    """

    def __init__(self, raw_conn, pool):
        self._conn = raw_conn
        self._pool = pool
        self._returned = False

    def cursor(self, *args, **kwargs):
        if "cursor_factory" not in kwargs:
            kwargs["cursor_factory"] = RealDictCursor
        raw_cur = self._conn.cursor(*args, **kwargs)
        return PooledCursorWrapper(raw_cur)

    def execute(self, sql, params=None):
        cur = self.cursor()
        cur.execute(sql, params)
        return cur

    def commit(self):
        return self._conn.commit()

    def rollback(self):
        return self._conn.rollback()

    def close(self):
        if not self._returned:
            self._returned = True
            try:
                # If transaction is in progress or uncommitted, rollback to leave connection clean
                if not self._conn.closed and self._conn.status != psycopg2.extensions.STATUS_READY:
                    self._conn.rollback()
            except Exception as e:
                logger.warning("Error rolling back uncommitted connection before returning to pool: %s", e)
            try:
                self._pool.putconn(self._conn)
            except Exception as e:
                logger.error("Error returning connection to pool: %s", e)

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        if exc_type is not None:
            try:
                self.rollback()
            except Exception:
                pass
        self.close()

    def __getattr__(self, name):
        return getattr(self._conn, name)


@contextmanager
def get_db_connection():
    """
    Context manager to borrow a connection from the pool and return it automatically on exit.
    Usage:
        with get_db_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT ...")
    """
    conn = get_connection()
    try:
        yield conn
    finally:
        conn.close()


@contextmanager
def get_db_cursor(commit: bool = False):
    """
    Context manager to borrow a connection and yield a RealDictCursor directly.
    Usage:
        with get_db_cursor(commit=True) as cur:
            cur.execute("INSERT ...")
    """
    conn = get_connection()
    try:
        cur = conn.cursor()
        try:
            yield cur
            if commit:
                conn.commit()
        finally:
            cur.close()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def get_connection():
    """
    Returns an active database connection.
    - If DATABASE_URL is set in environment/.env, checks out a thread-safe connection
      from PostgreSQL ThreadedConnectionPool wrapped in PooledConnectionWrapper (RealDictCursor).
    - If DATABASE_URL is not set, falls back to SQLite connection for smooth incremental transition.
    """
    if is_postgres_configured():
        pool = get_pool()
        if pool is not None:
            try:
                raw_conn = pool.getconn()
                # Validate connection is alive; if broken, retry once with fresh connection
                if raw_conn.closed != 0:
                    try:
                        pool.putconn(raw_conn, close=True)
                    except Exception:
                        pass
                    raw_conn = pool.getconn()
                return PooledConnectionWrapper(raw_conn, pool)
            except Exception as e:
                logger.error("Failed to checkout connection from PostgreSQL pool: %s", e)
                raise

    # Fallback to SQLite (preserves current ERP operation prior to full schema migration)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


POSTGRES_SCHEMA_PATH = Path(__file__).resolve().parent / "schema_postgres.sql"


def get_postgres_schema_sql() -> str:
    """Return the raw PostgreSQL multi-tenant schema DDL SQL."""
    if POSTGRES_SCHEMA_PATH.exists():
        return POSTGRES_SCHEMA_PATH.read_text(encoding="utf-8")
    raise FileNotFoundError(f"PostgreSQL schema file not found at {POSTGRES_SCHEMA_PATH}")


def init_postgres_db(conn=None):
    """
    Execute PostgreSQL DDL schema creating all 18 multi-tenant tables,
    the companies master table, exact NUMERIC columns, and composite indices.
    If conn is provided, executes on it; otherwise borrows a connection from the pool.
    """
    ddl_sql = get_postgres_schema_sql()
    should_close = False
    if conn is None:
        conn = get_connection()
        should_close = True

    try:
        with conn.cursor() as cur:
            cur.execute(ddl_sql)
        conn.commit()
        logger.info("PostgreSQL multi-tenant schema initialized successfully.")
    except Exception as e:
        logger.error("Failed to initialize PostgreSQL multi-tenant schema: %s", e)
        conn.rollback()
        raise
    finally:
        if should_close:
            conn.close()


def init_db():
    """Initialize database schema according to the active database engine."""
    if is_postgres_configured():
        init_postgres_db()
    else:
        init_sqlite_db()


def init_sqlite_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
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
                name TEXT UNIQUE NOT NULL,
                commission_rate REAL DEFAULT 0,
                show_on_website BOOLEAN DEFAULT 1
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
                commission_rate REAL DEFAULT 0,
                commission_amount REAL DEFAULT 0,
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
                cost_price REAL DEFAULT 0,
                commission_amount REAL DEFAULT 0
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

            CREATE TABLE IF NOT EXISTS warehouses (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT UNIQUE NOT NULL,
                location TEXT,
                commission_rate REAL DEFAULT 0,
                commission_applies INTEGER DEFAULT 0,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );

            CREATE TABLE IF NOT EXISTS warehouse_inventory (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                warehouse_id INTEGER REFERENCES warehouses(id),
                product_id INTEGER REFERENCES products(id),
                stock_quantity REAL DEFAULT 0,
                UNIQUE(warehouse_id, product_id)
            );

            CREATE TABLE IF NOT EXISTS suppliers (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                contact_name TEXT,
                phone TEXT,
                address TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );

            CREATE TABLE IF NOT EXISTS inventory_transfers (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                source_warehouse_id INTEGER REFERENCES warehouses(id),
                destination_warehouse_id INTEGER REFERENCES warehouses(id),
                notes TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );

            CREATE TABLE IF NOT EXISTS inventory_transfer_items (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                transfer_id INTEGER REFERENCES inventory_transfers(id),
                product_id INTEGER REFERENCES products(id),
                quantity REAL NOT NULL
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
            
        # Safely add warehouse_id to users, sales, inventory_history, purchases
        tables_to_add_warehouse = ['users', 'sales', 'inventory_history', 'purchases']
        for t in tables_to_add_warehouse:
            try:
                conn.execute(f"ALTER TABLE {t} ADD COLUMN warehouse_id INTEGER REFERENCES warehouses(id)")
                conn.commit()
            except sqlite3.OperationalError:
                pass

        try:
            conn.execute("ALTER TABLE sales ADD COLUMN commission_rate REAL DEFAULT 0")
            conn.commit()
        except sqlite3.OperationalError:
            pass

        try:
            conn.execute("ALTER TABLE sales ADD COLUMN commission_amount REAL DEFAULT 0")
            conn.commit()
        except sqlite3.OperationalError:
            pass

        try:
            conn.execute("ALTER TABLE warehouses ADD COLUMN commission_rate REAL DEFAULT 0")
            conn.commit()
        except sqlite3.OperationalError:
            pass
            
        try:
            conn.execute("ALTER TABLE sale_items ADD COLUMN commission_amount REAL DEFAULT 0")
            conn.commit()
        except sqlite3.OperationalError:
            pass
            
        try:
            conn.execute("ALTER TABLE warehouses ADD COLUMN commission_applies INTEGER DEFAULT 0")
            conn.commit()
        except sqlite3.OperationalError:
            pass
            
        try:
            conn.execute("ALTER TABLE brands ADD COLUMN commission_rate REAL DEFAULT 0")
            conn.commit()
        except sqlite3.OperationalError:
            pass

        try:
            conn.execute("ALTER TABLE brands ADD COLUMN show_on_website BOOLEAN DEFAULT 1")
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

        # Safely add show_in_brochure column to products table
        try:
            conn.execute("ALTER TABLE products ADD COLUMN show_in_brochure INTEGER DEFAULT 1")
            conn.commit()
        except sqlite3.OperationalError:
            pass
            
        # Safely add show_in_brochure column to brands table
        try:
            conn.execute("ALTER TABLE brands ADD COLUMN show_in_brochure INTEGER DEFAULT 1")
            conn.commit()
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
        _migrate_expenses(conn)
        _seed_default_data(conn)
        _ensure_sqlite_companies_support(conn)
    finally:
        conn.close()


def _migrate_expenses(conn):
    """Add expenses table if it doesn't exist (safe to run on existing DBs)."""
    conn.execute("""
        CREATE TABLE IF NOT EXISTS expenses (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            date        TEXT NOT NULL,
            category    TEXT NOT NULL,
            description TEXT,
            amount      REAL NOT NULL,
            added_by    INTEGER REFERENCES users(id),
            created_at  TEXT DEFAULT (datetime('now'))
        )
    """)
    conn.commit()


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

    # Seed Main Warehouse if not exists
    cur.execute("SELECT id FROM warehouses WHERE name = 'Main Warehouse'")
    if cur.fetchone() is None:
        cur.execute("INSERT INTO warehouses (name, location) VALUES ('Main Warehouse', 'Headquarters')")
        main_warehouse_id = cur.lastrowid
        print("Created default 'Main Warehouse'")
        
        # Optionally, migrate stock_quantity from products to warehouse_inventory for the main warehouse
        cur.execute("""
            INSERT OR IGNORE INTO warehouse_inventory (warehouse_id, product_id, stock_quantity)
            SELECT ?, id, COALESCE(stock_quantity, 0) FROM products
        """, (main_warehouse_id,))
        
        # Set all users except admin to main warehouse, set all sales, purchases, inventory_history
        cur.execute("UPDATE users SET warehouse_id = ? WHERE warehouse_id IS NULL AND role != 'admin'", (main_warehouse_id,))
        cur.execute("UPDATE sales SET warehouse_id = ? WHERE warehouse_id IS NULL", (main_warehouse_id,))
        cur.execute("UPDATE purchases SET warehouse_id = ? WHERE warehouse_id IS NULL", (main_warehouse_id,))
        cur.execute("UPDATE inventory_history SET warehouse_id = ? WHERE warehouse_id IS NULL", (main_warehouse_id,))
        
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


def get_company(company_id: int = 1):
    """
    Fetch company metadata by id, with default fallback for Company 1 (AK Distributors LLC)
    in legacy SQLite or unmigrated environments.
    """
    if not company_id:
        company_id = 1

    conn = get_connection()
    try:
        placeholder = "%s" if is_postgres_configured() else "?"
        cur = conn.cursor()
        try:
            cur.execute(f"SELECT * FROM companies WHERE id = {placeholder}", (company_id,))
            row = cur.fetchone()
            if row is not None:
                return dict(row)
        except Exception:
            # Table companies might not exist yet in legacy SQLite mode
            pass
    finally:
        conn.close()

    # Fallback default for Company 1 (AK Distributors LLC)
    if company_id == 1:
        return {
            "id": 1,
            "name": "AK Distributors LLC",
            "slug": "ak-distributors",
            "currency": "$",
            "invoice_prefix": "AK-",
            "starting_invoice_number": 1,
            "bill_address": "813 S 12th St",
            "ship_address": "Philadelphia PA 19147",
            "phone": "267-270-4200",
            "email": "akdistributorsllc@gmail.com",
            "tax_id": "",
            "logo_url": None,
            "max_warehouses": 5,
            "is_active": True,
        }
    return None


def get_user_by_id(user_id: int):
    conn = get_connection()
    try:
        placeholder = "%s" if is_postgres_configured() else "?"
        cur = conn.cursor()
        cur.execute(f"SELECT * FROM users WHERE id = {placeholder}", (user_id,))
        row = cur.fetchone()
        if row is None:
            return None
        res = dict(row)
        if "company_id" not in res or res["company_id"] is None:
            res["company_id"] = 1
        return res
    finally:
        conn.close()


def get_user_by_username(username: str):
    conn = get_connection()
    try:
        placeholder = "%s" if is_postgres_configured() else "?"
        cur = conn.cursor()
        cur.execute(f"SELECT * FROM users WHERE username = {placeholder}", (username,))
        row = cur.fetchone()
        if row is None:
            return None
        res = dict(row)
        if "company_id" not in res or res["company_id"] is None:
            res["company_id"] = 1
        return res
    finally:
        conn.close()


def generate_company_slug(name: str) -> str:
    """Generate a collision-proof URL slug for a newly registered company."""
    base = re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")
    if not base:
        base = "company"

    conn = get_connection()
    try:
        placeholder = "%s" if is_postgres_configured() else "?"
        cur = conn.cursor()
        slug = base
        counter = 2
        while True:
            try:
                cur.execute(f"SELECT id FROM companies WHERE slug = {placeholder}", (slug,))
                row = cur.fetchone()
                if not row:
                    return slug
            except Exception:
                return slug
            slug = f"{base}-{counter}"
            counter += 1
    finally:
        conn.close()


def _ensure_sqlite_companies_support(conn):
    """Ensure companies table and company_id columns exist across all multi-tenant tables when running in SQLite mode."""
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS companies (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            slug TEXT UNIQUE NOT NULL,
            currency TEXT DEFAULT '$',
            invoice_prefix TEXT DEFAULT 'INV-',
            starting_invoice_number INTEGER DEFAULT 1,
            bill_address TEXT,
            ship_address TEXT,
            phone TEXT,
            email TEXT,
            tax_id TEXT,
            logo_url TEXT,
            max_warehouses INTEGER DEFAULT 5,
            is_active INTEGER DEFAULT 1,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
        """
    )
    # Ensure default Company 1 (AK Distributors LLC) exists
    cur = conn.execute("SELECT id FROM companies WHERE id = 1")
    if not cur.fetchone():
        conn.execute(
            """
            INSERT INTO companies (id, name, slug, currency, invoice_prefix, starting_invoice_number, is_active)
            VALUES (1, 'AK Distributors LLC', 'ak-distributors', '$', 'INV-', 1, 1)
            """
        )

    multi_tenant_tables = [
        "users", "warehouses", "categories", "brands", "suppliers", "customers",
        "products", "product_variants", "warehouse_inventory", "sales", "sale_items",
        "customer_payments", "purchases", "purchase_items", "supplier_payments",
        "expenses", "inventory_transfers", "inventory_transfer_items", "inventory_history"
    ]
    for tbl in multi_tenant_tables:
        try:
            table_check = conn.execute("SELECT name FROM sqlite_master WHERE type='table' AND name=?", (tbl,)).fetchone()
            if not table_check:
                continue
            cols = [r[1] for r in conn.execute(f"PRAGMA table_info({tbl})").fetchall()]
            if "company_id" not in cols:
                conn.execute(f"ALTER TABLE {tbl} ADD COLUMN company_id INTEGER REFERENCES companies(id)")
                conn.execute(f"UPDATE {tbl} SET company_id = 1 WHERE company_id IS NULL")
        except Exception as e:
            logger.warning("Could not add company_id to %s in SQLite: %s", tbl, e)
    conn.commit()


def register_company_with_admin(
    company_name: str,
    admin_username: str,
    admin_password_hash: str,
    currency: str = "$",
    invoice_prefix: str = "INV-",
) -> tuple[int, int]:
    """
    Registers a new company and its root admin user in a single atomic transaction.
    Provisions a default 'Main Warehouse' and starter categories.
    Returns (company_id, user_id).
    """
    slug = generate_company_slug(company_name)
    conn = get_connection()
    try:
        is_pg = is_postgres_configured()
        if not is_pg:
            _ensure_sqlite_companies_support(conn)

        cur = conn.cursor()
        p = "%s" if is_pg else "?"

        # 1. Insert Company
        if is_pg:
            cur.execute(
                f"""
                INSERT INTO companies (name, slug, currency, invoice_prefix, starting_invoice_number, is_active)
                VALUES ({p}, {p}, {p}, {p}, 1, TRUE)
                RETURNING id
                """,
                (company_name, slug, currency, invoice_prefix),
            )
            company_id = cur.fetchone()["id"]
        else:
            cur.execute(
                f"""
                INSERT INTO companies (name, slug, currency, invoice_prefix, starting_invoice_number, is_active)
                VALUES ({p}, {p}, {p}, {p}, 1, 1)
                """,
                (company_name, slug, currency, invoice_prefix),
            )
            company_id = cur.lastrowid

        # 2. Insert Default 'Main Warehouse'
        if is_pg:
            cur.execute(
                f"""
                INSERT INTO warehouses (company_id, name, location)
                VALUES ({p}, {p}, {p})
                RETURNING id
                """,
                (company_id, "Main Warehouse", "Headquarters"),
            )
            warehouse_id = cur.fetchone()["id"]
        else:
            cur.execute(
                f"""
                INSERT INTO warehouses (company_id, name, location)
                VALUES ({p}, {p}, {p})
                """,
                (company_id, "Main Warehouse", "Headquarters"),
            )
            warehouse_id = cur.lastrowid

        # 3. Insert Starter Categories
        starter_categories = ["General", "Food", "Beverages", "Spices", "Other"]
        for cat in starter_categories:
            cur.execute(
                f"INSERT INTO categories (company_id, name) VALUES ({p}, {p})",
                (company_id, cat),
            )

        # 4. Insert Root Admin User
        if is_pg:
            cur.execute(
                f"""
                INSERT INTO users (company_id, username, password_hash, role, is_active, warehouse_id)
                VALUES ({p}, {p}, {p}, 'admin', TRUE, {p})
                RETURNING id
                """,
                (company_id, admin_username, admin_password_hash, warehouse_id),
            )
            user_id = cur.fetchone()["id"]
        else:
            cur.execute(
                f"""
                INSERT INTO users (company_id, username, password_hash, role, is_active, warehouse_id)
                VALUES ({p}, {p}, {p}, 'admin', 1, {p})
                """,
                (company_id, admin_username, admin_password_hash, warehouse_id),
            )
            user_id = cur.lastrowid

        conn.commit()
        logger.info(
            "Successfully provisioned new company '%s' (id=%d, slug='%s') with admin '%s'",
            company_name,
            company_id,
            slug,
            admin_username,
        )
        return company_id, user_id
    except Exception as e:
        conn.rollback()
        logger.error("Failed to register company '%s': %s", company_name, e)
        raise
    finally:
        conn.close()


def get_public_products(company_id: int = 1):
    conn = get_connection()
    try:
        cur = conn.execute(
            """
            SELECT p.id, p.name, p.brand, p.image_url, c.name as category_name
            FROM products p
            LEFT JOIN categories c ON p.category_id = c.id
            LEFT JOIN brands b ON (p.brand = b.name AND (b.company_id = p.company_id OR b.company_id IS NULL))
            WHERE p.company_id = ? AND p.is_public = 1 AND (b.show_on_website IS NULL OR b.show_on_website = 1)
            ORDER BY p.name COLLATE NOCASE
            """,
            (company_id,),
        )
        return [dict(row) for row in cur.fetchall()]
    finally:
        conn.close()


def get_brochure_products(company_id: int = 1):
    conn = get_connection()
    try:
        cur = conn.execute(
            """
            SELECT p.id, p.name, p.brand, p.image_url, c.name as category_name
            FROM products p
            LEFT JOIN categories c ON p.category_id = c.id
            LEFT JOIN brands b ON (p.brand = b.name AND (b.company_id = p.company_id OR b.company_id IS NULL))
            WHERE p.company_id = ? 
              AND (p.show_in_brochure IS NULL OR p.show_in_brochure = 1) 
              AND (b.show_in_brochure IS NULL OR b.show_in_brochure = 1)
            ORDER BY p.name COLLATE NOCASE
            """,
            (company_id,),
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


