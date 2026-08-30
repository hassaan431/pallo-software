import sqlite3

def run():
    conn = sqlite3.connect("database.db")
    cursor = conn.cursor()
    
    print("Starting warehouse migration...")
    
    # 1. Create warehouses table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS warehouses (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT UNIQUE NOT NULL,
            location TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    # 2. Create warehouse_inventory table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS warehouse_inventory (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            warehouse_id INTEGER REFERENCES warehouses(id),
            product_id INTEGER REFERENCES products(id),
            stock_quantity REAL DEFAULT 0,
            UNIQUE(warehouse_id, product_id)
        )
    ''')
    
    # 3. Create Main Warehouse if it doesn't exist
    cursor.execute("SELECT id FROM warehouses WHERE name = 'Main Warehouse'")
    row = cursor.fetchone()
    if not row:
        cursor.execute("INSERT INTO warehouses (name, location) VALUES ('Main Warehouse', 'Headquarters')")
        main_warehouse_id = cursor.lastrowid
        print("Created 'Main Warehouse'.")
    else:
        main_warehouse_id = row[0]
        print("Found 'Main Warehouse'.")
        
    def add_column(table, column_def):
        try:
            cursor.execute(f"ALTER TABLE {table} ADD COLUMN {column_def}")
            print(f"Added {column_def} to {table}")
        except sqlite3.OperationalError as e:
            if "duplicate column name" in str(e).lower() or "duplicate column" in str(e).lower():
                pass
            else:
                print(f"Error adding {column_def} to {table}:", e)

    # 4. Add warehouse_id to other tables
    add_column("users", "warehouse_id INTEGER REFERENCES warehouses(id)")
    add_column("sales", "warehouse_id INTEGER REFERENCES warehouses(id)")
    add_column("purchases", "warehouse_id INTEGER REFERENCES warehouses(id)")
    add_column("inventory_history", "warehouse_id INTEGER REFERENCES warehouses(id)")
    
    # Update existing nulls to the main warehouse
    cursor.execute("UPDATE users SET warehouse_id = ? WHERE warehouse_id IS NULL AND role != 'admin'", (main_warehouse_id,))
    cursor.execute("UPDATE sales SET warehouse_id = ? WHERE warehouse_id IS NULL", (main_warehouse_id,))
    
    # Only update purchases if the table exists
    try:
        cursor.execute("UPDATE purchases SET warehouse_id = ? WHERE warehouse_id IS NULL", (main_warehouse_id,))
    except sqlite3.OperationalError:
        pass
        
    cursor.execute("UPDATE inventory_history SET warehouse_id = ? WHERE warehouse_id IS NULL", (main_warehouse_id,))
    
    # 5. Migrate stock_quantity from products to warehouse_inventory
    # Using INSERT OR IGNORE so it is idempotent
    cursor.execute("""
        INSERT OR IGNORE INTO warehouse_inventory (warehouse_id, product_id, stock_quantity)
        SELECT ?, id, COALESCE(stock_quantity, 0) FROM products
    """, (main_warehouse_id,))
    print(f"Migrated product stock to warehouse_inventory (Warehouse {main_warehouse_id}).")
    
    conn.commit()
    conn.close()
    print("Migration complete!")

if __name__ == '__main__':
    run()
