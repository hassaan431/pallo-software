import re
with open("app.py", "r") as f:
    c = f.read()

# Fix inventory_edit
c = re.sub(
    r'(def inventory_edit\(product_id\):\s*conn = get_connection\(\)\s*try:\s*cur = conn\.execute\("SELECT id, stock_quantity FROM products WHERE id = \?", \(product_id,\)\))',
    r'def inventory_edit(product_id):\n    wid = current_user.warehouse_id or 1\n    conn = get_connection()\n    try:\n        cur = conn.execute("SELECT id FROM products WHERE id = ?", (product_id,))',
    c
)

c = re.sub(
    r'(old_stock = float\(existing\["stock_quantity"\] or 0\))',
    r'old_stock_row = conn.execute("SELECT stock_quantity FROM warehouse_inventory WHERE product_id = ? AND warehouse_id = ?", (product_id, wid)).fetchone()\n            old_stock = float(old_stock_row["stock_quantity"] if old_stock_row else 0)',
    c
)

c = re.sub(
    r'(update_query = """\s*UPDATE products\s*SET name = \?, category_id = \?, brand = \?, unit = \?, cost_price = \?, selling_price = \?, stock_quantity = \?, is_public = \?, supplier_id = \?, is_open = \?\s*""")',
    r'update_query = """\n                UPDATE products\n                SET name = ?, category_id = ?, brand = ?, unit = ?, cost_price = ?, selling_price = ?, is_public = ?, supplier_id = ?, is_open = ?\n            """',
    c
)

c = re.sub(
    r'(params = \[product_name, category_id, brand or None, unit, cost_price, selling_price, new_stock, is_public, supplier_id, is_open\])',
    r'params = [product_name, category_id, brand or None, unit, cost_price, selling_price, is_public, supplier_id, is_open]',
    c
)

c = re.sub(
    r'(if old_stock != new_stock:\n\s*conn\.execute\(\n\s*"""\n\s*INSERT INTO inventory_history \(product_id, transaction_type, quantity_change, previous_stock, new_stock, reference, supplier_id, warehouse_id\))',
    r'if old_stock != new_stock:\n                conn.execute("INSERT INTO warehouse_inventory (product_id, warehouse_id, stock_quantity) VALUES (?, ?, ?) ON CONFLICT(product_id, warehouse_id) DO UPDATE SET stock_quantity = ?", (product_id, wid, new_stock, new_stock))\n                conn.execute(\n                    """\n                    INSERT INTO inventory_history (product_id, transaction_type, quantity_change, previous_stock, new_stock, reference, supplier_id, warehouse_id)',
    c
)

with open("app.py", "w") as f:
    f.write(c)
