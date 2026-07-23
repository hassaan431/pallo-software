import sqlite3
import sys
from pathlib import Path

def aggregate_duplicates():
    # Use the same database path resolution as the main app
    db_path = Path(__file__).resolve().parent / "database.db"
    
    if not db_path.exists():
        print(f"Error: Database not found at {db_path}")
        sys.exit(1)
        
    print(f"Connecting to database at: {db_path}")
    conn = sqlite3.connect(db_path)
    cur = conn.cursor()
    
    # Get all products grouped by lowercase name
    cur.execute("SELECT LOWER(name), COUNT(*), SUM(stock_quantity), MIN(id) FROM products GROUP BY LOWER(name) HAVING COUNT(*) > 1")
    duplicates = cur.fetchall()
    
    if not duplicates:
        print("No duplicates found. The database is already clean!")
    
    for row in duplicates:
        name_lower, count, total_stock, primary_id = row
        print(f"Aggregating {count} duplicates for '{name_lower}' into product ID {primary_id} with total stock {total_stock}")
        
        # Update the primary product with the aggregated stock
        cur.execute("UPDATE products SET stock_quantity = ? WHERE id = ?", (total_stock, primary_id))
        
        # Delete the duplicates
        cur.execute("DELETE FROM products WHERE LOWER(name) = ? AND id != ?", (name_lower, primary_id))
    
    conn.commit()
    conn.close()
    print("Aggregation complete. The database has been cleaned.")

if __name__ == '__main__':
    aggregate_duplicates()
