import sys

with open("app.py", "r") as f:
    content = f.read()

route_code = """
@app.route("/inventory/adjust_stock", methods=["POST"])
@admin_required
def inventory_adjust_stock():
    product_id = int(request.form.get("product_id", 0))
    warehouse_id = int(request.form.get("warehouse_id", session.get("warehouse_id", 0)))
    new_stock = request.form.get("new_stock", "").strip()

    if not product_id or warehouse_id <= 0 or not new_stock:
        flash("Invalid request for stock adjustment.", "error")
        return redirect(url_for("inventory"))

    try:
        new_stock = float(new_stock)
    except ValueError:
        flash("Invalid stock quantity.", "error")
        return redirect(url_for("inventory"))

    conn = get_connection()
    try:
        old_stock_row = conn.execute("SELECT stock_quantity FROM warehouse_inventory WHERE product_id = ? AND warehouse_id = ?", (product_id, warehouse_id)).fetchone()
        old_stock = old_stock_row["stock_quantity"] if old_stock_row else 0.0

        if old_stock != new_stock:
            conn.execute("INSERT INTO warehouse_inventory (product_id, warehouse_id, stock_quantity) VALUES (?, ?, ?) ON CONFLICT(warehouse_id, product_id) DO UPDATE SET stock_quantity = ?", (product_id, warehouse_id, new_stock, new_stock))
            
            adjustment = new_stock - old_stock
            conn.execute(
                "INSERT INTO inventory_history (product_id, change_amount, reason, reference_id, date, warehouse_id) VALUES (?, ?, ?, ?, CURRENT_TIMESTAMP, ?)",
                (product_id, adjustment, "Manual Adjustment", None, warehouse_id)
            )
            conn.commit()
            flash("Stock adjusted successfully.", "success")
        else:
            flash("No changes made to stock.", "info")
    except Exception as e:
        print(f"Error adjusting stock: {e}")
        flash("Failed to adjust stock.", "error")
    finally:
        conn.close()

    return redirect(url_for("inventory"))
"""

target = '@app.route("/inventory/delete/<int:product_id>", methods=["POST"])'
if target in content:
    content = content.replace(target, route_code + "\n\n" + target)
    with open("app.py", "w") as f:
        f.write(content)
    print("Added adjust_stock route.")
else:
    print("Could not find target in app.py")
