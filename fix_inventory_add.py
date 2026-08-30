import re
with open("app.py", "r") as f:
    c = f.read()

new_logic = """@app.route("/inventory/add", methods=["POST"])
@admin_required
def inventory_add():
    product_name = (request.form.get("product_name") or "").strip()
    brand = (request.form.get("brand") or "").strip()
    if brand == "__add_new__":
        brand = ""
    unit = (request.form.get("unit") or "Each").strip()
    category_id_raw = (request.form.get("category_id") or "").strip()
    created_at = (request.form.get("created_at") or "").strip()
    is_public = 1 if request.form.get("is_public") else 0
    is_open = 1 if request.form.get("is_open") else 0
    supplier_id = request.form.get("supplier_id")

    try:
        category_id = int(category_id_raw)
        cost_price = float(request.form.get("cost_price") or 0)
        selling_price = float(request.form.get("selling_price") or 0)
        stock_quantity = float(request.form.get("stock_quantity") or 0)
    except ValueError:
        return redirect(url_for("inventory"))

    if not product_name or not category_id:
        return redirect(url_for("inventory"))

    import os
    from werkzeug.utils import secure_filename
    image_file = request.files.get("product_image")
    image_url = None
    if image_file and image_file.filename:
        filename = secure_filename(image_file.filename)
        base, _ = os.path.splitext(filename)
        filename = f"{base}.webp"
        
        upload_folder = os.path.join(app.root_path, "static", "uploads", "products")
        os.makedirs(upload_folder, exist_ok=True)
        filepath = os.path.join(upload_folder, filename)
        
        try:
            from PIL import Image
            img = Image.open(image_file)
            if img.mode != 'RGB':
                img = img.convert('RGB')
            img.thumbnail((800, 800))
            img.save(filepath, format="WEBP", optimize=True, quality=70)
        except Exception:
            # Fallback if Pillow fails
            image_file.seek(0)
            image_file.save(filepath)
            
        image_url = f"/static/uploads/products/{filename}"

    conn = get_connection()
    try:
        conn.execute("BEGIN")
        
        # Determine supplier
        if supplier_id:
            try:
                supplier_id = int(supplier_id)
            except ValueError:
                supplier_id = None
        
        if not supplier_id and brand:
            cur_sup = conn.execute("SELECT id FROM suppliers WHERE name = ?", (brand,))
            sup_row = cur_sup.fetchone()
            if sup_row:
                supplier_id = sup_row["id"]
            else:
                conn.execute("INSERT INTO suppliers (name) VALUES (?)", (brand,))
                supplier_id = conn.execute("SELECT last_insert_rowid()").fetchone()[0]
        
        # Check if product already exists
        wid = current_user.warehouse_id or 1
        cur = conn.execute("SELECT id, stock_quantity FROM products WHERE LOWER(name) = LOWER(?)", (product_name,))
        existing = cur.fetchone()
        
        if existing:
            product_id = existing["id"]
            old_stock_row = conn.execute("SELECT stock_quantity FROM warehouse_inventory WHERE product_id = ? AND warehouse_id = ?", (product_id, wid)).fetchone()
            old_stock = float(old_stock_row["stock_quantity"] if old_stock_row else 0)
            
            update_query = \"\"\"
                UPDATE products
                SET category_id = ?, brand = ?, unit = ?, cost_price = ?, selling_price = ?, supplier_id = ?, is_open = ?
            \"\"\"
            params = [category_id, brand or None, unit, cost_price, selling_price, supplier_id, is_open]
            
            if created_at:
                update_query += ", created_at = ?"
                params.append(created_at)
                
            if image_url:
                update_query += ", image_url = ?"
                params.append(image_url)
            update_query += " WHERE id = ?"
            params.append(product_id)
            
            conn.execute(update_query, params)
            
            new_stock = old_stock + stock_quantity
            if stock_quantity > 0:
                conn.execute("INSERT INTO warehouse_inventory (product_id, warehouse_id, stock_quantity) VALUES (?, ?, ?) ON CONFLICT(warehouse_id, product_id) DO UPDATE SET stock_quantity = ?", (product_id, wid, new_stock, new_stock))
                conn.execute(\"\"\"
                    INSERT INTO inventory_history (product_id, transaction_type, quantity_change, previous_stock, new_stock, reference, warehouse_id)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                \"\"\", (product_id, 'IN', stock_quantity, old_stock, new_stock, 'Manual Addition', wid))
        else:
            fields = ["name", "category_id", "brand", "unit", "cost_price", "selling_price", "is_public", "supplier_id", "is_open"]
            vals = ["?", "?", "?", "?", "?", "?", "?", "?", "?"]
            params_insert = [product_name, category_id, brand or None, unit, cost_price, selling_price, is_public, supplier_id, is_open]
            
            if created_at:
                fields.append("created_at")
                vals.append("?")
                params_insert.append(created_at)
            
            if image_url:
                fields.append("image_url")
                vals.append("?")
                params_insert.append(image_url)
                
            conn.execute(f"INSERT INTO products ({', '.join(fields)}) VALUES ({', '.join(vals)})", params_insert)
            product_id = conn.execute("SELECT last_insert_rowid()").fetchone()[0]
            
            if stock_quantity > 0:
                conn.execute("INSERT INTO warehouse_inventory (product_id, warehouse_id, stock_quantity) VALUES (?, ?, ?)", (product_id, wid, stock_quantity))
                conn.execute(\"\"\"
                    INSERT INTO inventory_history (product_id, transaction_type, quantity_change, previous_stock, new_stock, reference, warehouse_id)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                \"\"\", (product_id, 'IN', stock_quantity, 0, stock_quantity, 'Initial Stock', wid))

        # Keep brands table in sync for the Brand dropdown.
        if brand:
            conn.execute("INSERT OR IGNORE INTO brands (name) VALUES (?)", (brand,))

        conn.commit()
    finally:
        conn.close()

    return redirect(url_for("inventory"))"""

# I need to use regex to replace from `@app.route("/inventory/add"` up to `return redirect(url_for("inventory"))`
pattern = r'@app\.route\("/inventory/add".*?return redirect\(url_for\("inventory"\)\)'
c = re.sub(pattern, new_logic, c, flags=re.DOTALL)

with open("app.py", "w") as f:
    f.write(c)
