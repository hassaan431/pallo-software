import re
with open("app.py", "r") as f:
    c = f.read()

# I will rewrite the top half of the dashboard function to dynamically build the WHERE clauses.
new_dashboard_top = """def dashboard():
    warehouse_id = request.args.get("warehouse_id")
    if current_user.role != 'admin':
        warehouse_id = current_user.warehouse_id
        
    conn = get_connection()
    try:
        warehouses = conn.execute("SELECT id, name FROM warehouses ORDER BY name").fetchall()
        
        # Build conditions
        today = date.today().isoformat()
        now = date.today()
        current_month = f"{now.month:02d}"
        current_year = str(now.year)
        
        daily_cond = "invoice_date = ?"
        daily_params = [today]
        month_cond = "strftime('%m', invoice_date) = ? AND strftime('%Y', invoice_date) = ?"
        month_params = [current_month, current_year]
        
        if warehouse_id:
            daily_cond += " AND warehouse_id = ?"
            daily_params.append(warehouse_id)
            month_cond += " AND warehouse_id = ?"
            month_params.append(warehouse_id)
            
        # Get today's sales
        daily_revenue_row = conn.execute(
            f'SELECT COALESCE(SUM(grand_total), 0) as total_revenue FROM sales WHERE {daily_cond}', 
            tuple(daily_params)
        ).fetchone()
        
        # For joins involving sales:
        daily_cost_cond = "s.invoice_date = ?"
        daily_cost_params = [today]
        month_cost_cond = "strftime('%m', s.invoice_date) = ? AND strftime('%Y', s.invoice_date) = ?"
        month_cost_params = [current_month, current_year]
        
        if warehouse_id:
            daily_cost_cond += " AND s.warehouse_id = ?"
            daily_cost_params.append(warehouse_id)
            month_cost_cond += " AND s.warehouse_id = ?"
            month_cost_params.append(warehouse_id)
            
        daily_cost_row = conn.execute(
            f'''SELECT COALESCE(SUM(si.qty * COALESCE(si.packing_multiplier, 1.0) * si.cost_price), 0) as total_cost 
               FROM sale_items si 
               JOIN sales s ON si.sale_id = s.id 
               WHERE {daily_cost_cond}''', 
            tuple(daily_cost_params)
        ).fetchone()
        
        daily_revenue = float(daily_revenue_row["total_revenue"] or 0)
        daily_cost = float(daily_cost_row["total_cost"] or 0)
        daily_profit = daily_revenue - daily_cost
        
        # Get monthly revenue and cost
        monthly_revenue_row = conn.execute(
            f"SELECT COALESCE(SUM(grand_total), 0) as total_revenue FROM sales WHERE {month_cond}",
            tuple(month_params)
        ).fetchone()
        monthly_cost_row = conn.execute(
            f'''SELECT COALESCE(SUM(si.qty * COALESCE(si.packing_multiplier, 1.0) * si.cost_price), 0) as total_cost 
               FROM sale_items si 
               JOIN sales s ON si.sale_id = s.id 
               WHERE {month_cost_cond}''',
            tuple(month_cost_params)
        ).fetchone()"""

c = re.sub(
    r'def dashboard\(\):\s*conn = get_connection\(\)\s*try:\s*# Get today\'s sales\s*today = date\.today\(\)\.isoformat\(\)\s*daily_revenue_row = conn\.execute\(\s*\'SELECT COALESCE\(SUM\(grand_total\), 0\) as total_revenue FROM sales WHERE invoice_date = \?\',\s*\(today,\)\s*\)\.fetchone\(\)\s*daily_cost_row = conn\.execute\(\s*\'\'\'SELECT COALESCE\(SUM\(si\.qty \* COALESCE\(si\.packing_multiplier, 1\.0\) \* si\.cost_price\), 0\) as total_cost\s*FROM sale_items si\s*JOIN sales s ON si\.sale_id = s\.id\s*WHERE s\.invoice_date = \?\'\'\',\s*\(today,\)\s*\)\.fetchone\(\)\s*daily_revenue = float\(daily_revenue_row\["total_revenue"\] or 0\)\s*daily_cost = float\(daily_cost_row\["total_cost"\] or 0\)\s*daily_profit = daily_revenue - daily_cost\s*# Get monthly revenue and cost\s*now = date\.today\(\)\s*current_month = now\.month\s*current_year = now\.year\s*monthly_revenue_row = conn\.execute\(\s*"SELECT COALESCE\(SUM\(grand_total\), 0\) as total_revenue FROM sales WHERE strftime\(\'%m\', invoice_date\) = \? AND strftime\(\'%Y\', invoice_date\) = \?",\s*\(f"\{current_month:02d\}", str\(current_year\)\)\s*\)\.fetchone\(\)\s*monthly_cost_row = conn\.execute\(\s*\'\'\'SELECT COALESCE\(SUM\(si\.qty \* COALESCE\(si\.packing_multiplier, 1\.0\) \* si\.cost_price\), 0\) as total_cost\s*FROM sale_items si\s*JOIN sales s ON si\.sale_id = s\.id\s*WHERE strftime\(\'%m\', s\.invoice_date\) = \? AND strftime\(\'%Y\', s\.invoice_date\) = \?\'\'\',\s*\(f"\{current_month:02d\}", str\(current_year\)\)\s*\)\.fetchone\(\)',
    new_dashboard_top,
    c
)

with open("app.py", "w") as f:
    f.write(c)
