import sqlite3

conn = sqlite3.connect('database.db')
conn.row_factory = sqlite3.Row
print(dict(conn.execute('SELECT * FROM sales WHERE id = 26').fetchone()))
