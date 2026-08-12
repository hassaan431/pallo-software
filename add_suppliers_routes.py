import re

with open("app.py", "r") as f:
    content = f.read()

suppliers_code = """
@app.route("/suppliers", methods=["GET"])
@admin_required
def suppliers_page():
    conn = get_connection()
    try:
        cur_suppliers = conn.execute("SELECT * FROM suppliers ORDER BY name COLLATE NOCASE")
        suppliers = [dict(r) for r in cur_suppliers.fetchall()]
        
        cur_brands = conn.execute("SELECT * FROM brands ORDER BY name COLLATE NOCASE")
        brands = [dict(r) for r in cur_brands.fetchall()]
        
        return render_template("suppliers.html", suppliers=suppliers, brands=brands)
    finally:
        conn.close()

@app.route("/suppliers/add", methods=["POST"])
@admin_required
def suppliers_add():
    name = request.form.get("name", "").strip()
    phone = request.form.get("phone", "").strip()
    address = request.form.get("address", "").strip()
    
    if not name:
        return "Supplier name is required.", 400
        
    conn = get_connection()
    try:
        conn.execute("INSERT INTO suppliers (name, phone, address) VALUES (?, ?, ?)", (name, phone, address))
        conn.commit()
    finally:
        conn.close()
    return redirect(url_for("suppliers_page"))

@app.route("/suppliers/edit/<int:supplier_id>", methods=["POST"])
@admin_required
def suppliers_edit(supplier_id):
    name = request.form.get("name", "").strip()
    phone = request.form.get("phone", "").strip()
    address = request.form.get("address", "").strip()
    
    if not name:
        return "Supplier name is required.", 400
        
    conn = get_connection()
    try:
        conn.execute("UPDATE suppliers SET name = ?, phone = ?, address = ? WHERE id = ?", (name, phone, address, supplier_id))
        conn.commit()
    finally:
        conn.close()
    return redirect(url_for("suppliers_page"))

@app.route("/suppliers/delete/<int:supplier_id>", methods=["POST"])
@admin_required
def suppliers_delete(supplier_id):
    conn = get_connection()
    try:
        conn.execute("DELETE FROM suppliers WHERE id = ?", (supplier_id,))
        conn.execute("UPDATE products SET supplier_id = NULL WHERE supplier_id = ?", (supplier_id,))
        conn.execute("UPDATE inventory_history SET supplier_id = NULL WHERE supplier_id = ?", (supplier_id,))
        conn.commit()
    finally:
        conn.close()
    return redirect(url_for("suppliers_page"))

@app.route("/brands/edit/<int:brand_id>", methods=["POST"])
@admin_required
def brands_edit(brand_id):
    name = request.form.get("name", "").strip()
    if not name:
        return "Brand name is required.", 400
        
    conn = get_connection()
    try:
        # Get old brand name
        old_brand_name = conn.execute("SELECT name FROM brands WHERE id = ?", (brand_id,)).fetchone()
        if old_brand_name:
            old_name = old_brand_name["name"]
            conn.execute("UPDATE brands SET name = ? WHERE id = ?", (name, brand_id))
            conn.execute("UPDATE products SET brand = ? WHERE brand = ?", (name, old_name))
        conn.commit()
    finally:
        conn.close()
    return redirect(url_for("suppliers_page"))

@app.route("/brands/delete/<int:brand_id>", methods=["POST"])
@admin_required
def brands_delete(brand_id):
    conn = get_connection()
    try:
        # Get old brand name
        old_brand_name = conn.execute("SELECT name FROM brands WHERE id = ?", (brand_id,)).fetchone()
        if old_brand_name:
            old_name = old_brand_name["name"]
            conn.execute("DELETE FROM brands WHERE id = ?", (brand_id,))
            conn.execute("UPDATE products SET brand = NULL WHERE brand = ?", (old_name,))
        conn.commit()
    finally:
        conn.close()
    return redirect(url_for("suppliers_page"))

"""

target = '@app.route("/products/list", methods=["GET"])'
if suppliers_code not in content:
    new_content = content.replace(target, suppliers_code + target)
    with open("app.py", "w") as f:
        f.write(new_content)
    print("Routes added successfully.")
else:
    print("Routes already exist.")
