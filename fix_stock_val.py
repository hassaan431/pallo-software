import re
with open("app.py", "r") as f:
    c = f.read()

c = re.sub(
    r'(stock_val_query = "SELECT COALESCE\(SUM\(COALESCE\(cost_price, 0\) \* COALESCE\(stock_quantity, 0\)\), 0\) AS total_stock_value FROM warehouse_inventory")',
    r'stock_val_query = "SELECT COALESCE(SUM(COALESCE(p.cost_price, 0) * COALESCE(wi.stock_quantity, 0)), 0) AS total_stock_value FROM warehouse_inventory wi JOIN products p ON wi.product_id = p.id"',
    c
)
c = re.sub(
    r'(low_stock_query = "SELECT COALESCE\(SUM\(CASE WHEN COALESCE\(stock_quantity, 0\) < 5 THEN 1 ELSE 0 END\), 0\) AS low_stock_count FROM warehouse_inventory")',
    r'low_stock_query = "SELECT COALESCE(SUM(CASE WHEN COALESCE(wi.stock_quantity, 0) < 5 THEN 1 ELSE 0 END), 0) AS low_stock_count FROM warehouse_inventory wi"',
    c
)
c = re.sub(
    r'(stock_val_query \+= " WHERE warehouse_id = \?")',
    r'stock_val_query += " WHERE wi.warehouse_id = ?"',
    c
)
c = re.sub(
    r'(low_stock_query \+= " WHERE warehouse_id = \?")',
    r'low_stock_query += " WHERE wi.warehouse_id = ?"',
    c
)

with open("app.py", "w") as f:
    f.write(c)
