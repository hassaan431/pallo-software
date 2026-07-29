import sqlite3
import os

DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "database.db")

def wipe_data():
    if not os.path.exists(DB_PATH):
        print("database.db not found!")
        return
        
    conn = sqlite3.connect(DB_PATH)
    try:
        cur = conn.cursor()
        # Delete data from tables, keeping users table intact
        cur.executescript("""
            DELETE FROM sale_items;
            DELETE FROM sales;
            DELETE FROM products;
            DELETE FROM customers;
            DELETE FROM brands;
            DELETE FROM categories;
            DELETE FROM sqlite_sequence WHERE name != 'users';
        """)
        conn.commit()
        print("Successfully wiped all sales, products, customers, brands, and categories!")
        print("User accounts (including admin) were preserved.")
    except Exception as e:
        print("Error wiping database:", e)
    finally:
        conn.close()

if __name__ == "__main__":
    wipe_data()
