import re
with open("app.py", "r") as f:
    c = f.read()

# Add warehouse_id to products_list
c = re.sub(
    r'(def products_list\(\):\n    conn = get_connection\(\)\n    try:)',
    r'def products_list():\n    warehouse_id = request.args.get("warehouse_id")\n    wid = int(warehouse_id) if warehouse_id else (current_user.warehouse_id or 1)\n    conn = get_connection()\n    try:',
    c
)

c = re.sub(
    r'(COALESCE\(\(SELECT SUM\(stock_quantity\) FROM warehouse_inventory WHERE product_id = p\.id\), 0\) AS stock_quantity,)',
    r'COALESCE((SELECT stock_quantity FROM warehouse_inventory WHERE product_id = p.id AND warehouse_id = ?), 0) AS stock_quantity,',
    c
)

c = re.sub(
    r'(FROM products p\n\s*LEFT JOIN brands b\n\s*ON LOWER\(b\.name\) = LOWER\(p\.brand\)\n\s*GROUP BY p\.id\n\s*"""\n\s*\))',
    r'FROM products p\n            LEFT JOIN brands b\n                ON LOWER(b.name) = LOWER(p.brand)\n            GROUP BY p.id\n            """,\n            (wid,)',
    c
)

# We also need to fix products_search?
c = re.sub(
    r'(def products_search\(\):\n    q = request\.args\.get\("q", ""\)\.strip\(\)\n    conn = get_connection\(\)\n    try:)',
    r'def products_search():\n    q = request.args.get("q", "").strip()\n    warehouse_id = request.args.get("warehouse_id")\n    wid = int(warehouse_id) if warehouse_id else (current_user.warehouse_id or 1)\n    conn = get_connection()\n    try:',
    c
)

c = re.sub(
    r'(stock_query = "COALESCE\(\(SELECT stock_quantity FROM warehouse_inventory WHERE product_id = products\.id AND warehouse_id = \?\), 0\)" if warehouse_id else "COALESCE\(\(SELECT SUM\(stock_quantity\) FROM warehouse_inventory WHERE product_id = products\.id\), 0\)")',
    r'stock_query = "COALESCE((SELECT stock_quantity FROM warehouse_inventory WHERE product_id = products.id AND warehouse_id = ?), 0)"',
    c
)

# Wait, in products_search, there is already logic for warehouse_id? Let's check what it was before.

with open("app.py", "w") as f:
    f.write(c)
