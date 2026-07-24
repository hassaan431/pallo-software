import sqlite3

conn = sqlite3.connect('database.db')
conn.row_factory = sqlite3.Row
try:
    rows = conn.execute('''
    SELECT 
        s.salesman_id,
        COALESCE(u.username, 'Admin') as salesman_name,
        COUNT(DISTINCT s.id) as invoice_count,
        COALESCE(SUM(si.amount), 0) as total_revenue,
        COALESCE(SUM(si.qty * si.cost_price), 0) as total_cost,
        (SELECT COALESCE(SUM(remaining_amount), 0) FROM sales s2 WHERE COALESCE(s2.salesman_id, 0) = COALESCE(s.salesman_id, 0)) as outstanding
    FROM sales s
    LEFT JOIN users u ON u.id = s.salesman_id
    JOIN sale_items si ON si.sale_id = s.id
    JOIN products p ON p.id = si.product_id
    WHERE s.customer_id IS NOT NULL AND s.invoice_date >= '2026-07-02' AND s.invoice_date <= '2026-07-31'
    GROUP BY s.salesman_id, u.username
    ORDER BY total_revenue DESC
    ''').fetchall()
    for r in rows:
        print(dict(r))
except Exception as e:
    print("ERROR:", e)
