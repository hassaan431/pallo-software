import re

with open("app.py", "r") as f:
    c = f.read()

# Fix create_purchase (4380)
# We need to extract warehouse_id
c = re.sub(
    r'(status = data\.get\("status", "received"\))',
    r'\1\n    warehouse_id_raw = data.get("warehouse_id")\n    wid = int(warehouse_id_raw) if warehouse_id_raw else (current_user.warehouse_id or 1)',
    c
)

c = re.sub(
    r'(INSERT INTO purchases \(supplier_id, reference_number, purchase_date, subtotal, other_charges, grand_total, amount_paid, remaining_amount, status\)\s*VALUES \(\?, \?, \?, \?, \?, \?, \?, \?, \?\))',
    r'INSERT INTO purchases (supplier_id, reference_number, purchase_date, subtotal, other_charges, grand_total, amount_paid, remaining_amount, status, warehouse_id)\n            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)',
    c
)

c = re.sub(
    r'(\(supplier_id, reference_number, purchase_date, subtotal, other_charges, grand_total, amount_paid, remaining_amount, status\))',
    r'(supplier_id, reference_number, purchase_date, subtotal, other_charges, grand_total, amount_paid, remaining_amount, status, wid)',
    c, count=1 # For create_purchase
)

c = re.sub(
    r'(cur = conn\.execute\("SELECT stock_quantity FROM products WHERE id = \?", \(pid,\)\))',
    r'cur = conn.execute("SELECT stock_quantity FROM warehouse_inventory WHERE product_id = ? AND warehouse_id = ?", (pid, wid))',
    c
)

c = re.sub(
    r'(conn\.execute\("UPDATE products SET stock_quantity = \? WHERE id = \?", \(new_stock, pid\)\))',
    r'conn.execute("UPDATE warehouse_inventory SET stock_quantity = ? WHERE product_id = ? AND warehouse_id = ?", (new_stock, pid, wid))',
    c
)

c = re.sub(
    r'(INSERT INTO inventory_history \(product_id, transaction_type, quantity_change, previous_stock, new_stock, reference, supplier_id\)\s*VALUES \(\?, \'IN\', \?, \?, \?, \?, \?\))',
    r'INSERT INTO inventory_history (product_id, transaction_type, quantity_change, previous_stock, new_stock, reference, supplier_id, warehouse_id)\n                    VALUES (?, \'IN\', ?, ?, ?, ?, ?, ?)',
    c
)

c = re.sub(
    r'(\(pid, qty, old_stock, new_stock, f"Purchase #\{purchase_id\}", supplier_id\))',
    r'(pid, qty, old_stock, new_stock, f"Purchase #{purchase_id}", supplier_id, wid)',
    c
)

# For update_purchase (4456)
c = re.sub(
    r'(status = data\.get\("status"\))',
    r'\1\n    warehouse_id_raw = data.get("warehouse_id")\n    wid = int(warehouse_id_raw) if warehouse_id_raw else (current_user.warehouse_id or 1)',
    c
)
c = re.sub(
    r'(conn\.execute\("""\s*UPDATE purchases\s*SET supplier_id = \?, reference_number = \?, purchase_date = \?, status = \?\s*WHERE id = \?\s*""",\s*\(supplier_id, reference_number, purchase_date, status, purchase_id\)\s*\))',
    r'''conn.execute("""
            UPDATE purchases 
            SET supplier_id = ?, reference_number = ?, purchase_date = ?, status = ?, warehouse_id = ?
            WHERE id = ?
        """, (supplier_id, reference_number, purchase_date, status, wid, purchase_id))''',
    c
)
c = re.sub(
    r'(cur = conn\.execute\("SELECT name, stock_quantity FROM products WHERE id = \?", \(pid,\)\.fetchone\(\))',
    r'cur = conn.execute("SELECT p.name, COALESCE((SELECT stock_quantity FROM warehouse_inventory WHERE product_id = p.id AND warehouse_id = ?), 0) as stock_quantity FROM products p WHERE p.id = ?", (wid, pid,)).fetchone()',
    c
)

c = re.sub(
    r'(INSERT INTO inventory_history \(product_id, transaction_type, quantity_change, previous_stock, new_stock, reference, supplier_id\)\s*VALUES \(\?, \?, \?, \?, \?, \?, \?\))',
    r'INSERT INTO inventory_history (product_id, transaction_type, quantity_change, previous_stock, new_stock, reference, supplier_id, warehouse_id)\n                        VALUES (?, ?, ?, ?, ?, ?, ?, ?)',
    c
)
c = re.sub(
    r'(\(pid, trans_type, abs\(diff\), current_stock, new_stock, f"Edit Purchase #\{purchase_id\}", supplier_id\))',
    r'(pid, trans_type, abs(diff), current_stock, new_stock, f"Edit Purchase #{purchase_id}", supplier_id, wid)',
    c
)

# For delete_purchase (4571)
c = re.sub(
    r'(purchase = cur\.fetchone\(\)\s*if not purchase:\s*return jsonify\(\{"ok": False, "error": "Purchase not found"\}\), 404\s*supplier_id = purchase\["supplier_id"\])',
    r'\1\n        wid = purchase["warehouse_id"] or 1',
    c
)

c = re.sub(
    r'(INSERT INTO inventory_history \(product_id, transaction_type, quantity_change, previous_stock, new_stock, reference, supplier_id\)\s*VALUES \(\?, \'OUT\', \?, \?, \?, \?, \?\))',
    r'INSERT INTO inventory_history (product_id, transaction_type, quantity_change, previous_stock, new_stock, reference, supplier_id, warehouse_id)\n                    VALUES (?, \'OUT\', ?, ?, ?, ?, ?, ?)',
    c
)

c = re.sub(
    r'(\(pid, qty, current_stock, new_stock, f"Delete Purchase #\{purchase_id\}", supplier_id\))',
    r'(pid, qty, current_stock, new_stock, f"Delete Purchase #{purchase_id}", supplier_id, wid)',
    c
)


with open("app.py", "w") as f:
    f.write(c)
