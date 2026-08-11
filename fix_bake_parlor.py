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
    
    # 1. Let's see exactly what's in the database
    cursor.execute("SELECT DISTINCT brand FROM products WHERE brand LIKE '%Parl%'")
    brands = cursor.fetchall()
    print("Found the following brands containing 'Parl':")
    for b in brands:
        # Print with brackets so we can see trailing spaces
        print(f" - [{b[0]}]")
        
    # 2. Update anything that looks like the typo
    cursor.execute("UPDATE products SET brand = 'Bake Parlor' WHERE brand LIKE '%Parlar%'")
    updated = cursor.rowcount
    
    if updated > 0:
        print(f"\nSuccess! Updated {updated} products containing 'Parlar' to 'Bake Parlor'.")
        conn.commit()
    else:
        print("\nNo rows were updated. If you still see the typo, let me know the exact spelling printed above!")
        
    conn.close()

if __name__ == "__main__":
    fix_bake_parlor()
