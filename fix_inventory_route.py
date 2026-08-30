import re
with open("app.py", "r") as f:
    c = f.read()

inventory_logic_top = """def inventory():
    brand_filter = request.args.get("brand", "").strip()
    date_from = request.args.get("date_from", "").strip()
    date_to = request.args.get("date_to", "").strip()
    open_only = request.args.get("open_only") == '1'
    warehouse_id = request.args.get("warehouse_id")
    if current_user.role != 'admin' and current_user.warehouse_id:
        warehouse_id = current_user.warehouse_id

    conn = get_connection()
    try:
        warehouses = conn.execute("SELECT id, name FROM warehouses ORDER BY name").fetchall()
        
        stock_select = "COALESCE((SELECT SUM(stock_quantity) FROM warehouse_inventory WHERE product_id = p.id), 0)"
        if warehouse_id:
            stock_select = f"COALESCE((SELECT stock_quantity FROM warehouse_inventory WHERE product_id = p.id AND warehouse_id = ?), 0)"
            
        query = f\"\"\"
            SELECT
                p.id,
                p.name,
                p.brand,
                p.unit,
                p.cost_price,
                p.selling_price,
                {stock_select} AS stock_quantity,
                p.image_url,
                p.is_public,
                p.category_id,
                p.created_at,
                p.supplier_id,
                p.is_open,
                c.name AS category_name
            FROM products p
            LEFT JOIN categories c ON p.category_id = c.id
            WHERE 1=1
        \"\"\"
        params = []
        if warehouse_id:
            params.append(warehouse_id)
            
        if brand_filter:
            query += " AND p.brand = ?"
            params.append(brand_filter)
        if date_from:
            query += " AND date(p.created_at) >= ?"
            params.append(date_from)
        if date_to:
            query += " AND DATE(p.created_at) <= ?"
            params.append(date_to)"""

c = re.sub(
    r'(def inventory\(\):\s*brand_filter = request\.args\.get\("brand", ""\)\.strip\(\)\s*date_from = request\.args\.get\("date_from", ""\)\.strip\(\)\s*date_to = request\.args\.get\("date_to", ""\)\.strip\(\)\s*open_only = request\.args\.get\("open_only"\) == \'1\'\s*conn = get_connection\(\)\s*try:\s*query = """\s*SELECT\s*p\.id,\s*p\.name,\s*p\.brand,\s*p\.unit,\s*p\.cost_price,\s*p\.selling_price,\s*p\.stock_quantity,\s*p\.image_url,\s*p\.is_public,\s*p\.category_id,\s*p\.created_at,\s*p\.supplier_id,\s*p\.is_open,\s*c\.name AS category_name\s*FROM products p\s*LEFT JOIN categories c ON p\.category_id = c\.id\s*WHERE 1=1\s*"""\s*params = \[\]\s*if brand_filter:\s*query \+= " AND p\.brand = \?"\s*params\.append\(brand_filter\)\s*if date_from:\s*query \+= " AND date\(p\.created_at\) >= \?"\s*params\.append\(date_from\)\s*if date_to:\s*query \+= " AND DATE\(p\.created_at\) <= \?"\s*params\.append\(date_to\))',
    inventory_logic_top,
    c
)

inventory_logic_bottom = """        stock_val_query = "SELECT COALESCE(SUM(COALESCE(p.cost_price, 0) * COALESCE(wi.stock_quantity, 0)), 0) AS total_stock_value FROM warehouse_inventory wi JOIN products p ON wi.product_id = p.id"
        stock_val_params = []
        if warehouse_id:
            stock_val_query += " WHERE wi.warehouse_id = ?"
            stock_val_params.append(warehouse_id)
        cur = conn.execute(stock_val_query, tuple(stock_val_params))
        total_stock_value = float(cur.fetchone()["total_stock_value"] or 0)

        low_stock_query = "SELECT COALESCE(SUM(CASE WHEN COALESCE(wi.stock_quantity, 0) < 5 THEN 1 ELSE 0 END), 0) AS low_stock_count FROM warehouse_inventory wi"
        low_stock_params = []
        if warehouse_id:
            low_stock_query += " WHERE wi.warehouse_id = ?"
            low_stock_params.append(warehouse_id)
        cur = conn.execute(low_stock_query, tuple(low_stock_params))
        low_stock_count = int(cur.fetchone()["low_stock_count"] or 0)"""

c = re.sub(
    r'(cur = conn\.execute\(\s*"""\s*SELECT COALESCE\(SUM\(COALESCE\(cost_price, 0\) \* COALESCE\(stock_quantity, 0\)\), 0\) AS total_stock_value\s*FROM products\s*"""\s*\)\s*total_stock_value = float\(cur\.fetchone\(\)\["total_stock_value"\] or 0\)\s*cur = conn\.execute\(\s*"""\s*SELECT\s*COALESCE\(SUM\(CASE WHEN COALESCE\(stock_quantity, 0\) < 5 THEN 1 ELSE 0 END\), 0\) AS low_stock_count\s*FROM products\s*"""\s*\)\s*low_stock_count = int\(cur\.fetchone\(\)\["low_stock_count"\] or 0\))',
    inventory_logic_bottom,
    c
)

c = re.sub(
    r'(return render_template\(\s*"inventory\.html",\s*products=products_list,\s*categories=categories_list,\s*total_stock_value=total_stock_value,\s*low_stock_count=low_stock_count,\s*total_products=len\(products_list\),\s*brand_filter=brand_filter,\s*date_from=date_from,\s*date_to=date_to,\s*open_only=open_only,\s*suppliers=suppliers_list\s*\))',
    r'return render_template(\n            "inventory.html",\n            products=products_list,\n            categories=categories_list,\n            total_stock_value=total_stock_value,\n            low_stock_count=low_stock_count,\n            total_products=len(products_list),\n            brand_filter=brand_filter,\n            date_from=date_from,\n            date_to=date_to,\n            open_only=open_only,\n            suppliers=suppliers_list,\n            warehouses=[dict(w) for w in warehouses],\n            current_warehouse_id=int(warehouse_id) if warehouse_id else None\n        )',
    c
)

with open("app.py", "w") as f:
    f.write(c)
