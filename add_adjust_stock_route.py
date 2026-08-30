import re
with open("app.py", "r") as f:
    c = f.read()

route_code = """
@app.route("/inventory/adjust_stock", methods=["POST"])
@login_required
def inventory_adjust_stock():
    product_id = int(request.form.get("product_id"))
    new_stock = float(request.form.get("new_stock") or 0)
    warehouse_id_raw = request.form.get("warehouse_id")
    wid = int(warehouse_id_raw) if warehouse_id_raw else (current_user.warehouse_id or 1)

    conn = get_connection()
    try:
        conn.execute("BEGIN")
        # Get old stock
        old_stock_row = conn.execute("SELECT stock_quantity FROM warehouse_inventory WHERE product_id = ? AND warehouse_id = ?", (product_id, wid)).fetchone()
        old_stock = float(old_stock_row["stock_quantity"] if old_stock_row else 0)

        if new_stock != old_stock:
            diff = new_stock - old_stock
            t_type = 'IN' if diff > 0 else 'ADJUSTMENT'
            
            # Update or insert warehouse inventory
            conn.execute("INSERT INTO warehouse_inventory (product_id, warehouse_id, stock_quantity) VALUES (?, ?, ?) ON CONFLICT(warehouse_id, product_id) DO UPDATE SET stock_quantity = ?", (product_id, wid, new_stock, new_stock))
            
            # Insert history
            conn.execute(\"\"\"
                INSERT INTO inventory_history (product_id, transaction_type, quantity_change, previous_stock, new_stock, reference, warehouse_id)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            \"\"\", (product_id, t_type, diff, old_stock, new_stock, 'Manual Adjustment', wid))
            
        conn.commit()
    except Exception as e:
        conn.rollback()
        flash(f"Error adjusting stock: {e}", "error")
    finally:
        conn.close()

    return redirect(url_for("inventory"))

"""

c = c.replace('@app.route("/inventory/history/<int:product_id>", methods=["GET"])', route_code + '\n@app.route("/inventory/history/<int:product_id>", methods=["GET"])')

with open("app.py", "w") as f:
    f.write(c)
