import sqlite3
import datetime
conn = sqlite3.connect('database.db')
today = datetime.date.today().strftime('%Y-%m-%d')
conn.execute("INSERT OR REPLACE INTO products (id, name, stock_quantity, cost_price) VALUES (999, 'Test Product', 100, 1.0)")
conn.execute("INSERT OR REPLACE INTO warehouse_inventory (product_id, warehouse_id, stock_quantity) VALUES (999, 1, 100)")
conn.execute("DELETE FROM sales WHERE id = 999")
conn.execute(f"INSERT INTO sales (id, invoice_number, status, warehouse_id, amount_paid, remaining_amount, grand_total, payment_type, invoice_date, customer_id) VALUES (999, 'Q-999', 'quote', 1, 0, 10, 10, 'cash', '{today}', 1)")
conn.execute("DELETE FROM sale_items WHERE sale_id = 999")
conn.execute("INSERT INTO sale_items (sale_id, product_id, qty, packing_multiplier, amount, rate, cost_price, commission_amount, description, print_dual_units) VALUES (999, 999, 5, 1, 10, 2, 1, 0, 'Test', 0)")
conn.commit()
