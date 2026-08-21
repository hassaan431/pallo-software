import sqlite3
import os

def cleanup_inventory_history(db_path='database.db'):
    if not os.path.exists(db_path):
        print(f"Error: {db_path} not found.")
        return
        
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()

    # Find all "Edit Restore" records
    cur.execute("SELECT * FROM inventory_history WHERE reference LIKE '%Edit Restore'")
    restore_records = cur.fetchall()
    
    deleted_count = 0
    updated_count = 0

    for restore in restore_records:
        # The base reference should be without " Restore"
        base_ref = restore['reference'].replace(' Restore', '')
        product_id = restore['product_id']
        
        # Find the corresponding "Edit" record for the same product and base reference
        # that happened after the restore record (id > restore['id'])
        cur.execute("""
            SELECT * FROM inventory_history 
            WHERE reference = ? AND product_id = ? AND id > ?
            ORDER BY id ASC LIMIT 1
        """, (base_ref, product_id, restore['id']))
        edit_record = cur.fetchone()
        
        if edit_record:
            # We have a matching pair.
            net_change = restore['quantity_change'] + edit_record['quantity_change']
            
            if abs(net_change) < 1e-6:
                # Net change is 0. Both records are useless. Delete both.
                cur.execute("DELETE FROM inventory_history WHERE id IN (?, ?)", (restore['id'], edit_record['id']))
                deleted_count += 2
            else:
                # Net change is non-zero. Consolidate into the Edit record.
                # The Edit record's previous_stock should be the restore record's previous_stock
                # The quantity_change should be net_change
                # The transaction_type should be IN if net_change > 0 else OUT
                trans_type = 'IN' if net_change > 0 else 'OUT'
                
                cur.execute("""
                    UPDATE inventory_history 
                    SET quantity_change = ?, previous_stock = ?, transaction_type = ?
                    WHERE id = ?
                """, (net_change, restore['previous_stock'], trans_type, edit_record['id']))
                updated_count += 1
                
                # Delete the restore record
                cur.execute("DELETE FROM inventory_history WHERE id = ?", (restore['id'],))
                deleted_count += 1
                
    conn.commit()
    conn.close()
    
    print(f"Cleanup complete! Deleted {deleted_count} useless/redundant records. Updated {updated_count} records to reflect net changes.")

if __name__ == '__main__':
    print("Starting cleanup of inventory history logs...")
    cleanup_inventory_history()
