import sqlite3

def add_columns():
    conn = sqlite3.connect('database.db')
    try:
        conn.execute("ALTER TABLE warehouses ADD COLUMN commission_rate REAL DEFAULT 0")
        print("Added commission_rate to warehouses")
    except Exception as e:
        print(f"warehouses: {e}")

    try:
        conn.execute("ALTER TABLE sales ADD COLUMN commission_rate REAL DEFAULT 0")
        print("Added commission_rate to sales")
    except Exception as e:
        print(f"sales rate: {e}")
        
    try:
        conn.execute("ALTER TABLE sales ADD COLUMN commission_amount REAL DEFAULT 0")
        print("Added commission_amount to sales")
    except Exception as e:
        print(f"sales amount: {e}")

    conn.commit()
    conn.close()

if __name__ == '__main__':
    add_columns()
