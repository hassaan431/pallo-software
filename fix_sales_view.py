import re
with open("app.py", "r") as f:
    c = f.read()

c = re.sub(
    r'(recent_sales\.append\(d\)\n    finally:)',
    r'recent_sales.append(d)\n        warehouses_rows = conn.execute("SELECT id, name FROM warehouses ORDER BY name").fetchall()\n        warehouses_list = [dict(r) for r in warehouses_rows]\n    finally:',
    c
)

c = re.sub(
    r'(return render_template\(\n        "sales\.html",\n        customers=customers_list,\n        recent_sales=recent_sales,\n        next_invoice_number=get_next_invoice_number\(\),\n        today=date\.today\(\)\.isoformat\(\),\n        users=users_list\n    \))',
    r'return render_template(\n        "sales.html",\n        customers=customers_list,\n        recent_sales=recent_sales,\n        next_invoice_number=get_next_invoice_number(),\n        today=date.today().isoformat(),\n        users=users_list,\n        warehouses=warehouses_list\n    )',
    c
)

with open("app.py", "w") as f:
    f.write(c)
