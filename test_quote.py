import json
from app import app
from database import get_connection

with app.test_client() as c:
    # 1. Insert a mock quote
    conn = get_connection()
    conn.execute("INSERT INTO sales (invoice_number, customer_id, invoice_date, status) VALUES (?, 3, ?, ?)", ('Q-000041', '2026-08-11', 'quote'))
    sale_id = conn.execute("SELECT id FROM sales WHERE invoice_number = 'Q-000041'").fetchone()[0]
    # insert mock sale item
    conn.execute("INSERT INTO sale_items (sale_id, product_id, qty, rate) VALUES (?, 1, 1, 100)", (sale_id,))
    # ensure product 1 has stock
    conn.execute("UPDATE products SET stock_quantity = 100 WHERE id = 1")
    conn.commit()
    conn.close()

    print("Created quote Q-000041 with ID", sale_id)
    
    # 2. Mark it as sale
    response = c.post(f"/sales/{sale_id}/mark_sale")
    print(response.get_json())
    
    # 3. Check DB
    conn = get_connection()
    sale = conn.execute("SELECT invoice_number, status FROM sales WHERE id = ?", (sale_id,)).fetchone()
    print("Sale in DB now:", dict(sale))
