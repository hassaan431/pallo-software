import sqlite3
from pathlib import Path
import sys

def fix_bake_parlor():
    if getattr(sys, 'frozen', False):
        db_path = Path(sys.executable).resolve().parent / "database.db"
    else:
        db_path = Path(__file__).resolve().parent / "database.db"
        
    print(f"Connecting to database at: {db_path}")
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    # Check how many products have the misspelled brand
    cursor.execute("SELECT COUNT(*) FROM products WHERE brand = 'Bake Parlar'")
    count = cursor.fetchone()[0]
    
    if count > 0:
        print(f"Found {count} products with brand 'Bake Parlar'. Updating to 'Bake Parlor'...")
        cursor.execute("UPDATE products SET brand = 'Bake Parlor' WHERE brand = 'Bake Parlar'")
        conn.commit()
        print("Update successful!")
    else:
        print("No products found with brand 'Bake Parlar'.")
        
    conn.close()

if __name__ == "__main__":
    fix_bake_parlor()
