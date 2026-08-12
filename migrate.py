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

    conn.commit()
    conn.close()
    print("Migration complete! Your live database should now be up to date.")

if __name__ == "__main__":
    migrate()
