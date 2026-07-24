import sqlite3

conn = sqlite3.connect('database.db')
conn.row_factory = sqlite3.Row
print(dict(conn.execute('SELECT id, payment_type, subtotal, grand_total, status, amount_paid, remaining_amount FROM sales ORDER BY id DESC LIMIT 1').fetchone()))
