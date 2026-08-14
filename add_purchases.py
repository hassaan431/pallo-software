import re

with open("app.py", "r") as f:
    content = f.read()

purchases_routes = """

@app.route("/purchases")
@login_required
def purchases():
    conn = get_connection()
    try:
        cur = conn.execute('''
            SELECT p.id, p.reference_number, p.purchase_date, p.grand_total, p.amount_paid, p.remaining_amount, p.status, s.name as supplier_name
            FROM purchases p
            LEFT JOIN suppliers s ON p.supplier_id = s.id
            ORDER BY p.purchase_date DESC, p.id DESC
        ''')
        rows = cur.fetchall()
    finally:
        conn.close()
    return render_template("purchases.html", purchases=rows)

@app.route("/purchases/new", methods=["GET", "POST"])
@admin_required
def new_purchase():
    if request.method == "GET":
        conn = get_connection()
        try:
            suppliers = conn.execute("SELECT id, name FROM suppliers ORDER BY name COLLATE NOCASE ASC").fetchall()
            products = conn.execute("SELECT id, name, cost_price, unit FROM products ORDER BY name COLLATE NOCASE ASC").fetchall()
        finally:
            conn.close()
        return render_template("purchase_new.html", suppliers=suppliers, products=products)
    else:
        # Save purchase logic
        data = request.json
        supplier_id = data.get("supplier_id")
        purchase_date = data.get("purchase_date")
        reference_number = data.get("reference_number", "")
        items = data.get("items", [])
        payment_amount = float(data.get("payment_amount", 0))
        payment_method = data.get("payment_method", "cash")

        if not supplier_id or not items:
            return jsonify({"ok": False, "error": "Missing supplier or items"}), 400

        conn = get_connection()
        try:
            conn.execute("BEGIN")
            
            subtotal = sum(float(item.get("qty", 0)) * float(item.get("cost_price", 0)) for item in items)
            grand_total = subtotal
            amount_paid = payment_amount
            remaining_amount = grand_total - amount_paid
            
            status = 'unpaid'
            if amount_paid >= grand_total:
                status = 'paid'
            elif amount_paid > 0:
                status = 'partial'

            cur = conn.execute('''
                INSERT INTO purchases (supplier_id, reference_number, purchase_date, subtotal, grand_total, amount_paid, remaining_amount, status)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            ''', (supplier_id, reference_number, purchase_date, subtotal, grand_total, amount_paid, remaining_amount, status))
            
            purchase_id = cur.lastrowid
            
            if amount_paid > 0:
                conn.execute('''
                    INSERT INTO supplier_payments (supplier_id, purchase_id, amount, payment_date, payment_method)
                    VALUES (?, ?, ?, ?, ?)
                ''', (supplier_id, purchase_id, amount_paid, purchase_date, payment_method))

            for item in items:
                qty = float(item["qty"])
                cost = float(item["cost_price"])
                pid = int(item["product_id"])
                amount = qty * cost
                
                conn.execute('''
                    INSERT INTO purchase_items (purchase_id, product_id, qty, cost_price, amount)
                    VALUES (?, ?, ?, ?, ?)
                ''', (purchase_id, pid, qty, cost, amount))
                
                # Update inventory
                cur = conn.execute("SELECT stock_quantity FROM products WHERE id = ?", (pid,))
                row = cur.fetchone()
                if row:
                    old_stock = row["stock_quantity"] or 0
                    new_stock = old_stock + qty
                    conn.execute("UPDATE products SET stock_quantity = ? WHERE id = ?", (new_stock, pid))
                    conn.execute('''
                        INSERT INTO inventory_history (product_id, transaction_type, quantity_change, previous_stock, new_stock, reference, supplier_id)
                        VALUES (?, 'IN', ?, ?, ?, ?, ?)
                    ''', (pid, qty, old_stock, new_stock, f"Purchase #{purchase_id}", supplier_id))

            conn.commit()
            return jsonify({"ok": True, "purchase_id": purchase_id})
        except Exception as e:
            conn.rollback()
            return jsonify({"ok": False, "error": str(e)}), 500
        finally:
            conn.close()

@app.route("/purchases/<int:purchase_id>")
@login_required
def purchase_detail(purchase_id):
    conn = get_connection()
    try:
        purchase = conn.execute('''
            SELECT p.*, s.name as supplier_name 
            FROM purchases p 
            LEFT JOIN suppliers s ON p.supplier_id = s.id 
            WHERE p.id = ?
        ''', (purchase_id,)).fetchone()
        
        items = conn.execute('''
            SELECT pi.*, pr.name as product_name
            FROM purchase_items pi
            LEFT JOIN products pr ON pi.product_id = pr.id
            WHERE pi.purchase_id = ?
        ''', (purchase_id,)).fetchall()
        
        payments = conn.execute('''
            SELECT * FROM supplier_payments WHERE purchase_id = ? ORDER BY payment_date DESC, id DESC
        ''', (purchase_id,)).fetchall()
    finally:
        conn.close()
        
    if not purchase:
        return "Purchase not found", 404
        
    return render_template("purchase_detail.html", purchase=purchase, items=items, payments=payments)

@app.route("/api/supplier_payments", methods=["POST"])
@admin_required
def add_supplier_payment():
    data = request.json
    supplier_id = data.get("supplier_id")
    purchase_id = data.get("purchase_id")
    amount = float(data.get("amount", 0))
    payment_date = data.get("payment_date")
    payment_method = data.get("payment_method", "cash")
    notes = data.get("notes", "")

    if not supplier_id or amount <= 0:
        return jsonify({"ok": False, "error": "Invalid data"}), 400

    conn = get_connection()
    try:
        conn.execute("BEGIN")
        conn.execute('''
            INSERT INTO supplier_payments (supplier_id, purchase_id, amount, payment_date, payment_method, notes)
            VALUES (?, ?, ?, ?, ?, ?)
        ''', (supplier_id, purchase_id, amount, payment_date, payment_method, notes))
        
        if purchase_id:
            cur = conn.execute("SELECT grand_total, amount_paid FROM purchases WHERE id = ?", (purchase_id,))
            purchase = cur.fetchone()
            if purchase:
                new_paid = purchase["amount_paid"] + amount
                new_remaining = purchase["grand_total"] - new_paid
                status = 'unpaid'
                if new_paid >= purchase["grand_total"]:
                    status = 'paid'
                elif new_paid > 0:
                    status = 'partial'
                
                conn.execute('''
                    UPDATE purchases SET amount_paid = ?, remaining_amount = ?, status = ? WHERE id = ?
                ''', (new_paid, new_remaining, status, purchase_id))
        conn.commit()
        return jsonify({"ok": True})
    except Exception as e:
        conn.rollback()
        return jsonify({"ok": False, "error": str(e)}), 500
    finally:
        conn.close()
"""

# Insert before if __name__ == "__main__":
content = content.replace('if __name__ == "__main__":', purchases_routes + '\nif __name__ == "__main__":')

with open("app.py", "w") as f:
    f.write(content)
