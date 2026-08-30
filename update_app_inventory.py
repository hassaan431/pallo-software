import re
with open("app.py", "r") as f:
    c = f.read()

# Remove stock_quantity from inventory_add
c = re.sub(
    r'stock_quantity = float\(request\.form\.get\("stock_quantity"\) or 0\)',
    r'',
    c
)

c = re.sub(
    r'old_stock_row = cur\.fetchone\(\)\n\s*old_stock = float\(old_stock_row\["stock_quantity"\] or 0\) if old_stock_row else 0\n\s*new_stock = float\(stock_quantity\)',
    r'',
    c
)

c = re.sub(
    r'stock_quantity = float\(existing\["stock_quantity"\] or 0\)\n\s*new_stock = float\(stock_quantity\)',
    r'',
    c
)

# Remove stock_quantity from INSERT and UPDATE in inventory_add and inventory_edit
c = re.sub(
    r'(SET name = \?, brand = \?, category_id = \?, unit = \?, cost_price = \?, selling_price = \?), stock_quantity = \?(, is_public = \?, supplier_id = \?, is_open = \?)',
    r'\1\2',
    c
)
c = re.sub(
    r'params = \[product_name, brand, category_id, unit, cost_price, selling_price, stock_quantity, is_public, supplier_id, is_open\]',
    r'params = [product_name, brand, category_id, unit, cost_price, selling_price, is_public, supplier_id, is_open]',
    c
)

c = re.sub(
    r'(SET category_id = \?, brand = \?, unit = \?, cost_price = \?, selling_price = \?), stock_quantity = \?(, supplier_id = \?, is_open = \?)',
    r'\1\2',
    c
)
c = re.sub(
    r'params = \[category_id, brand or None, unit, cost_price, selling_price, new_stock, supplier_id, is_open\]',
    r'params = [category_id, brand or None, unit, cost_price, selling_price, supplier_id, is_open]',
    c
)

c = re.sub(
    r'INSERT INTO products \(name, category_id, brand, unit, cost_price, selling_price, stock_quantity, is_public, supplier_id, is_open\)',
    r'INSERT INTO products (name, category_id, brand, unit, cost_price, selling_price, is_public, supplier_id, is_open)',
    c
)
c = re.sub(
    r'VALUES \(\?, \?, \?, \?, \?, \?, \?, \?, \?, \?\)',
    r'VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)',
    c
)
c = re.sub(
    r'params_insert = \[product_name, category_id, brand or None, unit, cost_price, selling_price, new_stock, is_public, supplier_id, is_open\]',
    r'params_insert = [product_name, category_id, brand or None, unit, cost_price, selling_price, is_public, supplier_id, is_open]',
    c
)

# Remove history insert from inventory_add and inventory_edit
c = re.sub(
    r'if new_stock != old_stock:.*?(?=\# Keep brands)',
    r'',
    c, flags=re.DOTALL
)

c = re.sub(
    r'product_id = cur_insert\.lastrowid\n\s*if new_stock > 0:.*?(?=\# Keep brands)',
    r'product_id = cur_insert.lastrowid\n        ',
    c, flags=re.DOTALL
)

with open("app.py", "w") as f:
    f.write(c)
