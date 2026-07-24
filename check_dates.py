import sqlite3

conn = sqlite3.connect('database.db')
conn.row_factory = sqlite3.Row
print(conn.execute('SELECT MIN(invoice_date), MAX(invoice_date) FROM sales').fetchone()[0:2])
