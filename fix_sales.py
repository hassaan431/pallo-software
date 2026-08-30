import re

with open("app.py", "r") as f:
    content = f.read()

# 1. Fix sales_new
# Find where salesman_id is retrieved, around line 1874
# Then add warehouse_id retrieval
content = re.sub(
    r'(salesman_id_raw = \(request\.form\.get\("salesman_id"\) or ""\)\.strip\(\))',
    r'\1\n    warehouse_id_raw = (request.form.get("warehouse_id") or "").strip()',
    content
)

# In sales_new, find the INSERT INTO sales and its params
content = re.sub(
    r'(INSERT INTO sales\s+\([\s\S]*?amount_paid, remaining_amount, salesman_id)\)',
    r'\1, warehouse_id)',
    content, count=1 # Only first one is sales_new
)

content = re.sub(
    r'(amount_paid,\s*remaining_amount,\s*salesman_id,\s*\),)',
    r'amount_paid,\n                    remaining_amount,\n                    salesman_id,\n                    int(warehouse_id_raw) if warehouse_id_raw else (current_user.warehouse_id or 1),\n                ),',
    content, count=1
)

# We also need to fix the stock validation and deduction in sales_new
content = re.sub(
    r'("SELECT stock_quantity, name FROM products WHERE id = \?",\s*\(product_id,\),\s*\)\s*row = cur\.fetchone\(\))',
    r'# warehouse_id comes from warehouse_id_raw or current_user.warehouse_id\n                    wid = int(warehouse_id_raw) if warehouse_id_raw else (current_user.warehouse_id or 1)\n                    cur = conn.execute("SELECT p.name, COALESCE((SELECT stock_quantity FROM warehouse_inventory WHERE product_id = p.id AND warehouse_id = ?), 0) as stock_quantity FROM products p WHERE p.id = ?", (wid, product_id,))\n                    row = cur.fetchone()',
    content
)

content = re.sub(
    r'(cur = conn\.execute\("SELECT stock_quantity FROM products WHERE id = \?", \(product_id,\)\)\s*row = cur\.fetchone\(\)\s*old_stock = float\(row\["stock_quantity"\] or 0\) if row else 0\s*upd = conn\.execute\(\s*"""\s*UPDATE products\s*SET stock_quantity = stock_quantity - \?\s*WHERE id = \? AND stock_quantity >= \?\s*""",\s*\(qty_total, product_id, qty_total\),\s*\))',
    r'''wid = int(warehouse_id_raw) if warehouse_id_raw else (current_user.warehouse_id or 1)
                    upd = conn.execute(
                        """
                        UPDATE warehouse_inventory
                        SET stock_quantity = stock_quantity - ?
                        WHERE product_id = ? AND warehouse_id = ? AND stock_quantity >= ?
                        """,
                        (qty_total, product_id, wid, qty_total),
                    )''',
    content
)

# Also need to fix pos_submit_order
content = re.sub(
    r'(invoice_number = get_next_invoice_number\(\))',
    r'\1\n    warehouse_id_raw = data.get("warehouse_id")\n    wid = int(warehouse_id_raw) if warehouse_id_raw else (current_user.warehouse_id or 1)',
    content
)

content = re.sub(
    r'(cur = conn\.execute\("SELECT name, stock_quantity FROM products WHERE id = \?", \(product_id,\)\))',
    r'cur = conn.execute("SELECT p.name, COALESCE((SELECT stock_quantity FROM warehouse_inventory WHERE product_id = p.id AND warehouse_id = ?), 0) as stock_quantity FROM products p WHERE p.id = ?", (wid, product_id,))',
    content
)

content = re.sub(
    r'(INSERT INTO sales\s+\([\s\S]*?amount_paid, remaining_amount, salesman_id)\)',
    r'\1, warehouse_id)',
    content
)

content = re.sub(
    r'(amount_paid, remaining_amount, current_user\.id\n\s*\))',
    r'amount_paid, remaining_amount, current_user.id, wid\n            )',
    content
)

content = re.sub(
    r'(upd = conn\.execute\(\s*"""\s*UPDATE products\s*SET stock_quantity = stock_quantity - \?\s*WHERE id = \? AND stock_quantity >= \?\s*""",\s*\(li\["qty"\], li\["product_id"\], li\["qty"\]\)\s*\))',
    r'''upd = conn.execute(
                """
                UPDATE warehouse_inventory
                SET stock_quantity = stock_quantity - ?
                WHERE product_id = ? AND warehouse_id = ? AND stock_quantity >= ?
                """,
                (li["qty"] * li.get("packing_multiplier", 1.0), li["product_id"], wid, li["qty"] * li.get("packing_multiplier", 1.0))
            )''',
    content
)

with open("app.py", "w") as f:
    f.write(content)

print("Applied replacements")
