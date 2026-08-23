import sqlite3
import shutil
import os
from collections import defaultdict

def consolidate_purchases():
    # 1. Backup database
    db_path = "database.db"
    backup_path = "database_backup_pre_consolidation.db"
    
    if os.path.exists(db_path):
        print(f"Creating backup of {db_path} to {backup_path}...")
        shutil.copy(db_path, backup_path)
    else:
        print(f"Error: {db_path} not found.")
        return

    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    
    try:
        conn.execute("BEGIN")
        
        # 2. Group purchases by supplier_id and purchase_date
        purchases = conn.execute("SELECT * FROM purchases").fetchall()
        groups = defaultdict(list)
        
        for p in purchases:
            if p["supplier_id"]:
                groups[(p["supplier_id"], p["purchase_date"])].append(dict(p))
        
        consolidation_count = 0
        
        for (supplier_id, p_date), group in groups.items():
            if len(group) > 1:
                print(f"Found {len(group)} shipments for supplier {supplier_id} on {p_date}. Consolidating...")
                
                # Sort group by ID so the oldest one becomes the master
                group.sort(key=lambda x: x["id"])
                master_purchase = group[0]
                master_id = master_purchase["id"]
                
                # Process the other purchases in the group
                for other in group[1:]:
                    other_id = other["id"]
                    print(f"  -> Moving items and payments from purchase #{other_id} to #{master_id}")
                    
                    # Move purchase_items
                    conn.execute("UPDATE purchase_items SET purchase_id = ? WHERE purchase_id = ?", (master_id, other_id))
                    
                    # Move supplier_payments
                    conn.execute("UPDATE supplier_payments SET purchase_id = ? WHERE purchase_id = ?", (master_id, other_id))
                    
                    # Update inventory_history reference
                    # The reference was logged as "Purchase #{id}"
                    conn.execute("UPDATE inventory_history SET reference = ? WHERE reference = ?", 
                                 (f"Purchase #{master_id}", f"Purchase #{other_id}"))
                    
                    # Delete the old purchase record
                    conn.execute("DELETE FROM purchases WHERE id = ?", (other_id,))
                    
                # Now recalculate totals for the master purchase
                items = conn.execute("SELECT qty, cost_price FROM purchase_items WHERE purchase_id = ?", (master_id,)).fetchall()
                subtotal = sum(float(item["qty"]) * float(item["cost_price"]) for item in items)
                
                # Aggregate other charges from all merged purchases
                total_other_charges = sum(float(p.get("other_charges", 0) or 0) for p in group)
                
                grand_total = subtotal + total_other_charges
                
                # Aggregate payments
                payments = conn.execute("SELECT amount FROM supplier_payments WHERE purchase_id = ?", (master_id,)).fetchall()
                amount_paid = sum(float(payment["amount"]) for payment in payments)
                
                remaining_amount = grand_total - amount_paid
                
                status = 'unpaid'
                if abs(remaining_amount) < 0.001 or amount_paid >= grand_total:
                    status = 'paid'
                    remaining_amount = 0
                elif amount_paid > 0:
                    status = 'partial'
                    
                conn.execute('''
                    UPDATE purchases
                    SET subtotal = ?, other_charges = ?, grand_total = ?, amount_paid = ?, remaining_amount = ?, status = ?
                    WHERE id = ?
                ''', (subtotal, total_other_charges, grand_total, amount_paid, remaining_amount, status, master_id))
                
                consolidation_count += 1
                
        conn.commit()
        print(f"\nSuccessfully consolidated {consolidation_count} groups of shipments.")
        print("Note: Inventory quantities were not disturbed, only the internal records were merged.")
        
    except Exception as e:
        conn.rollback()
        print(f"An error occurred: {e}. Changes have been rolled back.")
    finally:
        conn.close()

if __name__ == "__main__":
    confirm = input("This script will merge all shipments from the same supplier on the same day into single shipments. Proceed? (y/n): ")
    if confirm.lower() == 'y':
        consolidate_purchases()
    else:
        print("Aborted.")
