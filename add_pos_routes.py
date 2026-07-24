pos_routes = """
@app.route("/pos")
@login_required
def pos():
    # Only salesmen or admin can access
    return render_template("catalogue.html")

@app.route("/pos/submit_order", methods=["POST"])
@login_required
def pos_submit_order():
    data = request.json
    if not data:
        return jsonify({"ok": False, "error": "Invalid request format."}), 400

    customer_id = data.get("customer_id")
    customer_name = (data.get("customer_name") or "").strip()
    customer_phone = (data.get("customer_phone") or "").strip()
    customer_area = (data.get("customer_area") or "").strip()
    
    items = data.get("items", [])
    payment_type = data.get("payment_type", "cash")
    amount_paid = float(data.get("amount_paid") or 0)
    
    if not items:
        return jsonify({"ok": False, "error": "Cart is empty."}), 400

    invoice_date = date.today().isoformat()
    invoice_number = get_next_invoice_number()
    
    conn = get_connection()
    try:
        conn.execute("BEGIN")

        # Create customer if id not provided
        if not customer_id:
            if not customer_name:
                raise ValueError("Customer name is required.")
            cur = conn.execute(
                "INSERT INTO customers (name, phone, area) VALUES (?, ?, ?)",
                (customer_name, customer_phone, customer_area)
            )
            customer_id = int(cur.lastrowid)
        else:
            customer_id = int(customer_id)

        # Parse items and calculate totals
        subtotal = 0
        parsed_items = []
        for it in items:
            product_id = int(it["id"])
            qty = float(it["qty"])
            if qty <= 0:
                continue
            
            cur = conn.execute("SELECT name, selling_price, cost_price FROM products WHERE id = ?", (product_id,))
            row = cur.fetchone()
            if not row:
                raise ValueError(f"Invalid product ID {product_id}")
            
            rate = float(row["selling_price"] or 0)
            amount = round(qty * rate, 2)
            subtotal += amount
            
            parsed_items.append({
                "product_id": product_id,
                "description": row["name"],
                "qty": qty,
                "rate": rate,
                "amount": amount
            })

        if not parsed_items:
            raise ValueError("Cart has no valid items.")

        grand_total = round(subtotal, 2)

        # Payment status
        if payment_type in ['cash', 'cheque']:
            amount_paid = grand_total
            remaining_amount = 0
            status = 'paid'
        else:
            if amount_paid > grand_total:
                amount_paid = grand_total
            remaining_amount = grand_total - amount_paid
            if remaining_amount <= 0:
                remaining_amount = 0
                status = 'paid'
            elif amount_paid > 0:
                status = 'partial'
            else:
                status = 'unpaid'

        # Insert sale
        cur = conn.execute(
            \"\"\"
            INSERT INTO sales
                (invoice_number, customer_id, invoice_date, payment_type,
                 subtotal, grand_total, status, amount_paid, remaining_amount, salesman_id)
            VALUES
                (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            \"\"\",
            (
                invoice_number, customer_id, invoice_date, payment_type,
                subtotal, grand_total, status, amount_paid, remaining_amount, current_user.id
            )
        )
        sale_id = int(cur.lastrowid)

        # Insert items and deduct stock
        for li in parsed_items:
            conn.execute(
                \"\"\"
                INSERT INTO sale_items (sale_id, product_id, description, qty, rate, amount, cost_price)
                VALUES (?, ?, ?, ?, ?, ?, COALESCE((SELECT cost_price FROM products WHERE id = ?), 0))
                \"\"\",
                (sale_id, li["product_id"], li["description"], li["qty"], li["rate"], li["amount"], li["product_id"])
            )
            
            conn.execute(
                \"\"\"
                UPDATE products
                SET stock_quantity = COALESCE(stock_quantity, 0) - ?
                WHERE id = ?
                \"\"\",
                (li["qty"], li["product_id"])
            )

        conn.commit()
        return jsonify({"ok": True, "sale_id": sale_id, "invoice_number": invoice_number})

    except ValueError as e:
        conn.rollback()
        return jsonify({"ok": False, "error": str(e)}), 400
    except Exception as e:
        conn.rollback()
        return jsonify({"ok": False, "error": str(e)}), 500
    finally:
        conn.close()
"""

with open("app.py", "r") as f:
    content = f.read()

# Insert right before 'if __name__ == "__main__":'
content = content.replace('if __name__ == "__main__":', pos_routes + '\n\nif __name__ == "__main__":')

with open("app.py", "w") as f:
    f.write(content)
