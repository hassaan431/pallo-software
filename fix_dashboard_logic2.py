import re
with open("app.py", "r") as f:
    c = f.read()

recent_sales_replace = """        recent_sales_cond = ""
        recent_sales_params = []
        if warehouse_id:
            recent_sales_cond = "WHERE s.warehouse_id = ?"
            recent_sales_params.append(warehouse_id)
            
        recent_sales_rows = conn.execute(
            f'''
            SELECT
                s.id,
                s.invoice_number,
                s.invoice_date,
                c.name AS customer_name,
                s.grand_total,
                s.payment_type,
                s.status,
                (SELECT COALESCE(SUM(si.qty * COALESCE(si.packing_multiplier, 1.0) * si.cost_price), 0) FROM sale_items si WHERE si.sale_id = s.id) as total_cost
            FROM sales s
            LEFT JOIN customers c ON c.id = s.customer_id
            {recent_sales_cond}
            ORDER BY s.id DESC
            LIMIT 5
            ''', tuple(recent_sales_params)
        ).fetchall()"""

c = re.sub(
    r'(# Get recent sales \(last 5\)\s*recent_sales_rows = conn\.execute\(\s*"""\s*SELECT\s*s\.id,\s*s\.invoice_number,\s*s\.invoice_date,\s*c\.name AS customer_name,\s*s\.grand_total,\s*s\.payment_type,\s*s\.status,\s*\(SELECT COALESCE\(SUM\(si\.qty \* COALESCE\(si\.packing_multiplier, 1\.0\) \* si\.cost_price\), 0\) FROM sale_items si WHERE si\.sale_id = s\.id\) as total_cost\s*FROM sales s\s*LEFT JOIN customers c ON c\.id = s\.customer_id\s*ORDER BY s\.id DESC\s*LIMIT 5\s*"""\s*\)\.fetchall\(\))',
    recent_sales_replace,
    c
)

upcoming_payments_replace = """        upcoming_cond = "s.remaining_amount > 0 OR s.status = 'unpaid'"
        upcoming_params = []
        if warehouse_id:
            upcoming_cond = "(s.remaining_amount > 0 OR s.status = 'unpaid') AND s.warehouse_id = ?"
            upcoming_params.append(warehouse_id)
            
        upcoming_payments_rows = conn.execute(
            f'''
            SELECT
                s.id,
                s.invoice_number,
                s.invoice_date,
                s.due_date,
                c.name AS customer_name,
                c.phone AS customer_phone,
                s.remaining_amount
            FROM sales s
            LEFT JOIN customers c ON c.id = s.customer_id
            WHERE {upcoming_cond}
            ORDER BY s.due_date ASC
            LIMIT 10
            ''', tuple(upcoming_params)
        ).fetchall()"""

c = re.sub(
    r'(# Get upcoming/overdue payments \(limit 10\)\s*upcoming_payments_rows = conn\.execute\(\s*"""\s*SELECT\s*s\.id,\s*s\.invoice_number,\s*s\.invoice_date,\s*s\.due_date,\s*c\.name AS customer_name,\s*c\.phone AS customer_phone,\s*s\.remaining_amount\s*FROM sales s\s*LEFT JOIN customers c ON c\.id = s\.customer_id\s*WHERE s\.remaining_amount > 0 OR s\.status = \'unpaid\'\s*ORDER BY s\.due_date ASC\s*LIMIT 10\s*"""\s*\)\.fetchall\(\))',
    upcoming_payments_replace,
    c
)

stock_val_replace = """        stock_val_query = "SELECT COALESCE(SUM(COALESCE(cost_price, 0) * COALESCE(stock_quantity, 0)), 0) AS total_stock_value FROM warehouse_inventory"
        stock_val_params = []
        if warehouse_id:
            stock_val_query += " WHERE warehouse_id = ?"
            stock_val_params.append(warehouse_id)
            
        total_stock_value_row = conn.execute(stock_val_query, tuple(stock_val_params)).fetchone()
        
        low_stock_query = "SELECT COALESCE(SUM(CASE WHEN COALESCE(stock_quantity, 0) < 5 THEN 1 ELSE 0 END), 0) AS low_stock_count FROM warehouse_inventory"
        low_stock_params = []
        if warehouse_id:
            low_stock_query += " WHERE warehouse_id = ?"
            low_stock_params.append(warehouse_id)
            
        low_stock_count_row = conn.execute(low_stock_query, tuple(low_stock_params)).fetchone()"""

c = re.sub(
    r'(# Get inventory metrics\s*total_stock_value_row = conn\.execute\(\s*"""\s*SELECT COALESCE\(SUM\(COALESCE\(cost_price, 0\) \* COALESCE\(stock_quantity, 0\)\), 0\) AS total_stock_value\s*FROM products\s*"""\s*\)\.fetchone\(\)\s*low_stock_count_row = conn\.execute\(\s*"""\s*SELECT\s*COALESCE\(SUM\(CASE WHEN COALESCE\(stock_quantity, 0\) < 5 THEN 1 ELSE 0 END\), 0\) AS low_stock_count\s*FROM products\s*"""\s*\)\.fetchone\(\))',
    stock_val_replace,
    c
)

return_replace = """    return render_template(
        "dashboard.html",
        daily_revenue=daily_revenue,
        daily_profit=daily_profit,
        daily_net_profit=daily_net_profit,
        monthly_revenue=monthly_revenue,
        monthly_profit=monthly_profit,
        monthly_net_profit=monthly_net_profit,
        monthly_margin=monthly_margin,
        monthly_net_margin=monthly_net_margin,
        recent_sales=recent_sales,
        upcoming_payments=upcoming_payments,
        total_stock_value=float(total_stock_value_row["total_stock_value"] or 0),
        low_stock_count=int(low_stock_count_row["low_stock_count"] or 0),
        warehouses=warehouses,
        current_warehouse_id=int(warehouse_id) if warehouse_id else None
    )"""

c = re.sub(
    r'(return render_template\(\s*"dashboard\.html",\s*daily_revenue=daily_revenue,\s*daily_profit=daily_profit,\s*daily_net_profit=daily_net_profit,\s*monthly_revenue=monthly_revenue,\s*monthly_profit=monthly_profit,\s*monthly_net_profit=monthly_net_profit,\s*monthly_margin=monthly_margin,\s*monthly_net_margin=monthly_net_margin,\s*recent_sales=recent_sales,\s*upcoming_payments=upcoming_payments,\s*total_stock_value=float\(total_stock_value_row\["total_stock_value"\] or 0\),\s*low_stock_count=int\(low_stock_count_row\["low_stock_count"\] or 0\)\s*\))',
    return_replace,
    c
)

with open("app.py", "w") as f:
    f.write(c)
