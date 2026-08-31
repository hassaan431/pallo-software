import sqlite3
import sys

def run(invoice_number, new_warehouse_id):
    conn = sqlite3.connect("database.db")
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()

    try:
        # Find the sale
        sale = cur.execute("SELECT * FROM sales WHERE invoice_number = ?", (invoice_number,)).fetchone()
        if not sale:
            print(f"Error: Invoice {invoice_number} not found.")
            return

        old_warehouse_id = sale['warehouse_id']
        sale_id = sale['id']

        if old_warehouse_id == new_warehouse_id:
            print(f"Invoice {invoice_number} is already assigned to Warehouse ID {new_warehouse_id}.")
            return
            
        print(f"Moving {invoice_number} from Warehouse {old_warehouse_id} to Warehouse {new_warehouse_id}...")

        # Update the sale's warehouse
        cur.execute("UPDATE sales SET warehouse_id = ? WHERE id = ?", (new_warehouse_id, sale_id))

        # Re-allocate inventory for each item
        items = cur.execute("SELECT * FROM sale_items WHERE sale_id = ?", (sale_id,)).fetchall()
        for item in items:
            product_id = item['product_id']
            qty = item['qty']
            multiplier = item['packing_multiplier'] or 1.0
            total_qty = qty * multiplier
            
            print(f"  -> Product ID {product_id}: Reversing {total_qty} from Warehouse {old_warehouse_id}, deducting from Warehouse {new_warehouse_id}")

            # 1. Add back to old warehouse
            cur.execute("""
                UPDATE warehouse_inventory 
                SET stock_quantity = stock_quantity + ? 
                WHERE product_id = ? AND warehouse_id = ?
            """, (total_qty, product_id, old_warehouse_id))

            # 2. Deduct from new warehouse
            # (Create the row if it doesn't exist, though it should exist)
            cur.execute("""
                INSERT INTO warehouse_inventory (warehouse_id, product_id, stock_quantity)
                VALUES (?, ?, ?)
                ON CONFLICT(warehouse_id, product_id) DO UPDATE SET
                stock_quantity = stock_quantity - ?
            """, (new_warehouse_id, product_id, -total_qty, total_qty))

            # 3. Update inventory_history records for this sale item
            cur.execute("""
                UPDATE inventory_history 
                SET warehouse_id = ? 
                WHERE reference = ? AND product_id = ? AND transaction_type = 'Sale'
            """, (new_warehouse_id, invoice_number, product_id))
            
        conn.commit()
        print("Successfully updated invoice and corrected stock!")

    except Exception as e:
        conn.rollback()
        print(f"Error occurred: {e}")
    finally:
        conn.close()

if __name__ == "__main__":
    if len(sys.argv) != 3:
        print("Usage: python3 change_sale_warehouse.py <INVOICE_NUMBER> <NEW_WAREHOUSE_ID>")
        print("Example: python3 change_sale_warehouse.py AK-000101 2")
    else:
        run(sys.argv[1], int(sys.argv[2]))
