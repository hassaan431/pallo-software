import re
with open("app.py", "r") as f:
    c = f.read()

c = re.sub(
    r'(conn\.execute\("""\s*INSERT INTO inventory_history \(product_id, transaction_type, quantity_change, previous_stock, new_stock, reference\)\s*VALUES \(\?, \'OUT\', \?, \?, \?, \?\)\s*""", \(li\["product_id"\], -qty_deduct, old_stock, new_stock, f\'Invoice #\{invoice_number\}\'\)\))',
    r'conn.execute("""\n                    INSERT INTO inventory_history (product_id, transaction_type, quantity_change, previous_stock, new_stock, reference, warehouse_id)\n                    VALUES (?, \'OUT\', ?, ?, ?, ?, ?)\n                """, (li["product_id"], -qty_deduct, old_stock, new_stock, f\'Invoice #{invoice_number}\', wid))',
    c
)

with open("app.py", "w") as f:
    f.write(c)
