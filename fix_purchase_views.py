import re
with open("app.py", "r") as f:
    c = f.read()

c = re.sub(
    r'(return render_template\("purchase_new\.html", suppliers=suppliers, products=products, warehouses=warehouses)\)',
    r'\1, purchase=None)',
    c
)

c = re.sub(
    r'(suppliers = \[dict\(row\) for row in conn\.execute\("SELECT id, name FROM suppliers ORDER BY name COLLATE NOCASE ASC"\)\.fetchall\(\)\]\s*products = \[dict\(row\) for row in conn\.execute\("SELECT id, name, cost_price, unit FROM products ORDER BY name COLLATE NOCASE ASC"\)\.fetchall\(\)\])',
    r'\1\n        warehouses = [dict(row) for row in conn.execute("SELECT id, name FROM warehouses ORDER BY name").fetchall()]',
    c
)

c = re.sub(
    r'(return render_template\("purchase_new\.html", suppliers=suppliers, products=products, purchase=purchase)\)',
    r'\1, warehouses=warehouses)',
    c
)

with open("app.py", "w") as f:
    f.write(c)
