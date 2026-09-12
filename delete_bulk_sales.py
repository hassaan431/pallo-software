import sqlite3
import argparse

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--commit', action='store_true', help='Commit the transaction (default is dry-run)')
    args = parser.parse_args()

    conn = sqlite3.connect('database.db')
    conn.row_factory = sqlite3.Row
    
    # We want invoices between AK-000069 and AK-000111
    # We can generate the list of exact invoice numbers
    target_invoices = [f"AK-{str(i).zfill(6)}" for i in range(69, 112)]
    
    try:
        conn.execute("BEGIN")
        
        # Find all sales matching these invoices
        placeholders = ','.join(['?'] * len(target_invoices))
        sales = conn.execute(f"SELECT id, invoice_number, warehouse_id, grand_total, customer_id FROM sales WHERE invoice_number IN ({placeholders})", target_invoices).fetchall()
        
        if not sales:
            print("No sales found for the given invoice numbers.")
            return

        print(f"Found {len(sales)} sales to delete.")
        
        total_revenue = 0
        total_items_restored = 0
        
        for sale in sales:
            sale_id = sale["id"]
            invoice_number = sale["invoice_number"]
            wid = int(sale["warehouse_id"]) if sale["warehouse_id"] else 1
            total_revenue += float(sale["grand_total"] or 0)
            
            # Fetch items
            items = conn.execute(
                """
                SELECT product_id, qty, COALESCE(packing_multiplier, 1.0) as packing_multiplier
                FROM sale_items
                WHERE sale_id = ?
                """,
                (sale_id,),
            ).fetchall()
            
            # Delete items and sale
            conn.execute("DELETE FROM sale_items WHERE sale_id = ?", (sale_id,))
            conn.execute("DELETE FROM sales WHERE id = ?", (sale_id,))
            
            # Restore inventory
            for it in items:
                product_id = it["product_id"]
                restored_qty = float(it["qty"]) * float(it["packing_multiplier"])
                total_items_restored += restored_qty
                
                cur = conn.execute("SELECT stock_quantity FROM warehouse_inventory WHERE product_id = ? AND warehouse_id = ?", (product_id, wid))
                row = cur.fetchone()
                old_stock = float(row["stock_quantity"] or 0) if row else 0
                new_stock = old_stock + restored_qty
                
                conn.execute(
                    """
                    INSERT INTO warehouse_inventory (product_id, warehouse_id, stock_quantity)
                    VALUES (?, ?, ?)
                    ON CONFLICT(warehouse_id, product_id) DO UPDATE SET stock_quantity = ?
                    """,
                    (product_id, wid, new_stock, new_stock),
                )
                
                conn.execute("""
                    INSERT INTO inventory_history (product_id, transaction_type, quantity_change, previous_stock, new_stock, reference, warehouse_id)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                """, (product_id, 'IN', restored_qty, old_stock, new_stock, f'Invoice #{invoice_number} Bulk Deleted', wid))
                
        print(f"Total Revenue to be deducted: ${total_revenue:.2f}")
        print(f"Total Item Units to be restored to inventory: {total_items_restored}")
        
        if args.commit:
            conn.commit()
            print("\nSUCCESS: 40+ sales have been deleted, and inventory has been restored.")
        else:
            conn.rollback()
            print("\nDRY RUN: Transaction rolled back. No data was modified. Run with --commit to apply.")
            
    except Exception as e:
        conn.rollback()
        print(f"Error occurred: {e}")
    finally:
        conn.close()

if __name__ == '__main__':
    main()
