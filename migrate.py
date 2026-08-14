import sqlite3

def migrate():
    conn = sqlite3.connect("database.db")
    cursor = conn.cursor()

    try:
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS suppliers (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                contact_name TEXT,
                phone TEXT,
                address TEXT
            )
        ''')
        print("Suppliers table checked/created.")
    except Exception as e:
        print("Suppliers table error:", e)

    try:
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS product_variants (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                product_id INTEGER REFERENCES products(id),
                size TEXT,
                flavor TEXT,
                price_adjustment REAL DEFAULT 0
            )
        ''')
        print("Product_variants table checked/created.")
    except Exception as e:
        print("Product_variants table error:", e)

    def add_column(table, column_def):
        try:
            cursor.execute(f"ALTER TABLE {table} ADD COLUMN {column_def}")
            print(f"Added {column_def} to {table}")
        except sqlite3.OperationalError as e:
            if "duplicate column name" in str(e):
                pass
            else:
                print(f"Error adding {column_def} to {table}:", e)

    add_column("products", "supplier_id INTEGER REFERENCES suppliers(id)")
    add_column("products", "is_open INTEGER DEFAULT 0")
    add_column("inventory_history", "supplier_id INTEGER REFERENCES suppliers(id)")
    add_column("sale_items", "cost_price REAL DEFAULT 0")
    add_column("sale_items", "print_dual_units INTEGER DEFAULT 0")
    add_column("sale_items", "packing_multiplier REAL DEFAULT 1.0")
    add_column("purchases", "other_charges REAL DEFAULT 0")

    try:
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS purchases (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                supplier_id INTEGER REFERENCES suppliers(id),
                reference_number TEXT,
                purchase_date TEXT NOT NULL,
                subtotal REAL DEFAULT 0,
                discount_amount REAL DEFAULT 0,
                other_charges REAL DEFAULT 0,
                grand_total REAL DEFAULT 0,
                amount_paid REAL DEFAULT 0,
                remaining_amount REAL DEFAULT 0,
                status TEXT DEFAULT 'unpaid',
                notes TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        print("Purchases table checked/created.")
    except Exception as e:
        print("Purchases table error:", e)

    try:
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS purchase_items (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                purchase_id INTEGER REFERENCES purchases(id),
                product_id INTEGER REFERENCES products(id),
                qty REAL DEFAULT 1,
                cost_price REAL DEFAULT 0,
                amount REAL DEFAULT 0
            )
        ''')
        print("Purchase_items table checked/created.")
    except Exception as e:
        print("Purchase_items table error:", e)

    try:
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS supplier_payments (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                supplier_id INTEGER REFERENCES suppliers(id),
                purchase_id INTEGER REFERENCES purchases(id),
                amount REAL NOT NULL,
                payment_date TEXT NOT NULL,
                payment_method TEXT,
                notes TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        print("Supplier_payments table checked/created.")
    except Exception as e:
        print("Supplier_payments table error:", e)

    conn.commit()
    conn.close()
    print("Migration complete! Your live database should now be up to date.")

if __name__ == "__main__":
    migrate()
