import sqlite3
import argparse

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--commit', action='store_true', help='Commit the transaction (default is dry-run)')
    args = parser.parse_args()

    conn = sqlite3.connect('database.db')
    conn.row_factory = sqlite3.Row
    
    # LA Warehouse ID is 2
    warehouse_id = 2
    
    try:
        conn.execute("BEGIN")
        
        # Get warehouse name for logging
        wh = conn.execute("SELECT name FROM warehouses WHERE id = ?", (warehouse_id,)).fetchone()
        warehouse_name = wh["name"] if wh else f"Warehouse {warehouse_id}"
        
        # Find all products in LA Warehouse that have non-zero stock
        inventory_items = conn.execute(
            """
            SELECT product_id, stock_quantity 
            FROM warehouse_inventory 
            WHERE warehouse_id = ? AND stock_quantity != 0
            """, 
            (warehouse_id,)
        ).fetchall()
        
        if not inventory_items:
            print(f"No non-zero inventory found in {warehouse_name}.")
            return

        print(f"Found {len(inventory_items)} products with non-zero stock in {warehouse_name}.")
        
        total_units_removed = 0
        
        for item in inventory_items:
            product_id = item["product_id"]
            old_stock = float(item["stock_quantity"])
            
            # We want to bring the stock to 0, so the change is -old_stock
            quantity_change = -old_stock
            transaction_type = "OUT" if old_stock > 0 else "IN"
            
            total_units_removed += abs(quantity_change)
            
            # Update warehouse inventory to 0
            conn.execute(
                """
                UPDATE warehouse_inventory 
                SET stock_quantity = 0 
                WHERE product_id = ? AND warehouse_id = ?
                """,
                (product_id, warehouse_id),
            )
            
            # Record audit history
            conn.execute(
                """
                INSERT INTO inventory_history (
                    product_id, transaction_type, quantity_change, 
                    previous_stock, new_stock, reference, warehouse_id
                ) VALUES (?, ?, ?, ?, ?, ?, ?)
                """, 
                (product_id, transaction_type, abs(quantity_change), old_stock, 0, f"{warehouse_name} Bulk Reset", warehouse_id)
            )
                
        print(f"Total Item Units to be adjusted to zero: {total_units_removed}")
        
        if args.commit:
            conn.commit()
            print(f"\\nSUCCESS: Inventory for {warehouse_name} has been reset to 0.")
        else:
            conn.rollback()
            print("\\nDRY RUN: Transaction rolled back. No data was modified. Run with --commit to apply.")
            
    except Exception as e:
        conn.rollback()
        print(f"Error occurred: {e}")
    finally:
        conn.close()

if __name__ == '__main__':
    main()
