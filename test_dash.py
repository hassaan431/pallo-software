import sqlite3
from datetime import date, timedelta
def get_connection():
    conn = sqlite3.connect("database.db")
    conn.row_factory = sqlite3.Row
    return conn
def test():
    conn = get_connection()
    try:
        today = date.today().isoformat()
        daily_revenue_row = conn.execute(
            'SELECT COALESCE(SUM(grand_total), 0) as total_revenue FROM sales WHERE invoice_date = ?', 
            (today,)
        ).fetchone()
        daily_cost_row = conn.execute(
            '''SELECT COALESCE(SUM(si.qty * COALESCE(si.packing_multiplier, 1.0) * si.cost_price), 0) as total_cost 
               FROM sale_items si 
               JOIN sales s ON si.sale_id = s.id 
               WHERE s.invoice_date = ?''', 
            (today,)
        ).fetchone()
        daily_revenue = float(daily_revenue_row["total_revenue"] or 0)
        daily_cost = float(daily_cost_row["total_cost"] or 0)
        daily_profit = daily_revenue - daily_cost
        
        now = date.today()
        current_month = now.month
        current_year = now.year
        monthly_revenue_row = conn.execute(
            "SELECT COALESCE(SUM(grand_total), 0) as total_revenue FROM sales WHERE strftime('%m', invoice_date) = ? AND strftime('%Y', invoice_date) = ?",
            (f"{current_month:02d}", str(current_year))
        ).fetchone()
        monthly_cost_row = conn.execute(
            '''SELECT COALESCE(SUM(si.qty * COALESCE(si.packing_multiplier, 1.0) * si.cost_price), 0) as total_cost 
               FROM sale_items si 
               JOIN sales s ON si.sale_id = s.id 
               WHERE strftime('%m', s.invoice_date) = ? AND strftime('%Y', s.invoice_date) = ?''',
            (f"{current_month:02d}", str(current_year))
        ).fetchone()
        
        monthly_revenue = float(monthly_revenue_row["total_revenue"] or 0)
        monthly_cost = float(monthly_cost_row["total_cost"] or 0)
        monthly_profit = monthly_revenue - monthly_cost
        monthly_margin = round((monthly_profit / monthly_revenue * 100), 2) if monthly_revenue > 0 else 0
        
        recent_sales_rows = conn.execute(
            """
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
            ORDER BY s.id DESC
            LIMIT 5
            """
        ).fetchall()
        recent_sales = []
        for r in recent_sales_rows:
            d = dict(r)
            rev = float(d["grand_total"] or 0)
            cost = float(d["total_cost"] or 0)
            d["profit_margin"] = round(((rev - cost) / rev * 100), 2) if rev > 0 else 0
            d["profit_amount"] = round(rev - cost, 2)
            recent_sales.append(d)

        upcoming_payments_rows = conn.execute(
            """
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
            WHERE s.remaining_amount > 0
              AND s.due_date IS NOT NULL
              AND s.due_date != ''
            ORDER BY s.due_date ASC
            LIMIT 10
            """
        ).fetchall()
        upcoming_payments = [dict(r) for r in upcoming_payments_rows]
        
        thirty_days_ago = (date.today() - timedelta(days=30)).isoformat()
        daily_sales_rows = conn.execute(
            """
            SELECT invoice_date, SUM(grand_total) as daily_total
            FROM sales
            WHERE invoice_date >= ?
            GROUP BY invoice_date
            ORDER BY invoice_date ASC
            """,
            (thirty_days_ago,)
        ).fetchall()
        
        daily_sales_labels = [row["invoice_date"] for row in daily_sales_rows]
        daily_sales_data = [row["daily_total"] for row in daily_sales_rows]
        print("Success")
    except Exception as e:
        print("Error:", e)
test()
