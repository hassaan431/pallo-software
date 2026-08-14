import os
import json
import sqlite3

import csv

from datetime import date, timedelta

from collections import defaultdict

from database import get_connection, get_next_invoice_number, get_user_by_id, get_user_by_username, init_db, DB_PATH

init_db()

def fix_existing_sales_data():
    db = get_connection()
    try:
        # Fix ALL cash sales regardless 
        # of current amount_paid value
        db.execute("""
            UPDATE sales 
            SET amount_paid = grand_total,
                remaining_amount = 0,
                status = 'paid'
            WHERE payment_type = 'cash'
        """)
        # Fix ALL cheque sales
        db.execute("""
            UPDATE sales 
            SET amount_paid = grand_total,
                remaining_amount = 0,
                status = 'paid'
            WHERE payment_type = 'cheque'
        """)
        # Fix credit sales where BOTH 
        # amount_paid AND remaining_amount are 0
        # meaning they were never properly set
        db.execute("""
            UPDATE sales 
            SET amount_paid = 0,
                remaining_amount = grand_total,
                status = 'unpaid'
            WHERE payment_type = 'credit'
            AND amount_paid = 0
            AND remaining_amount = 0
        """)
        db.commit()
        print("Sales data fix applied successfully")
    except Exception as e:
        print(f"Data fix error: {e}")
        db.rollback()
    finally:
        db.close()

fix_existing_sales_data()

from flask import Flask, Response, flash, jsonify, redirect, render_template, request, url_for
from flask_login import LoginManager, UserMixin, current_user, login_required, login_user, logout_user
from werkzeug.security import check_password_hash, generate_password_hash
from werkzeug.exceptions import HTTPException
from functools import wraps

from invoice_generator import generate_invoice_pdf

app = Flask(__name__)
app.secret_key = "change-this-secret-key-for-local-use"

from public_routes import public_bp
app.register_blueprint(public_bp)

login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = "login"
login_manager.login_message = None


class User(UserMixin):
    def __init__(self, db_id: int, username: str, role: str = 'admin'):
        self.id = db_id
        self.username = username
        self.role = role


@login_manager.user_loader
def load_user(user_id):
    if user_id is None:
        return None
    try:
        pk = int(user_id)
    except (TypeError, ValueError):
        return None
    row = get_user_by_id(pk)
    if row is None:
        return None
    is_active = row["is_active"] if "is_active" in row.keys() else 1
    if is_active == 0:
        return None
    role = row["role"] if "role" in row.keys() else "admin"
    return User(row["id"], row["username"], role)

def admin_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not current_user.is_authenticated:
            return redirect(url_for('login'))
        if current_user.role != 'admin':
            return redirect(url_for('pos'))
        return f(*args, **kwargs)
    return decorated_function

@app.template_filter("format_rate")
def format_rate_filter(val):
    try:
        v = float(val or 0)
        if abs(v - round(v, 2)) < 1e-5:
            return f"{v:.2f}"
        return f"{v:.4f}"
    except Exception:
        return "0.00"

@app.template_filter("brand_logo_filename")
def brand_logo_filename_filter(val):
    from database import get_brand_logo_filename
    return get_brand_logo_filename(val)





@app.route("/login", methods=["GET", "POST"])
def login():
    if current_user.is_authenticated:
        if current_user.role == 'salesman':
            return redirect(url_for("pos"))
        return redirect(url_for("dashboard"))
    if request.method == "POST":
        username = (request.form.get("username") or "").strip()
        password = request.form.get("password") or ""
        row = get_user_by_username(username)
        if row is not None and check_password_hash(row["password_hash"], password):
            is_active = row["is_active"] if "is_active" in row.keys() else 1
            if is_active == 0:
                return render_template(
                    "login.html",
                    error="Account is disabled. Please contact the administrator.",
                )
            role = row["role"] if "role" in row.keys() else "admin"
            user_obj = User(row["id"], row["username"], role)
            login_user(user_obj, remember=True)
            next_url = request.args.get("next")
            if next_url and next_url.startswith("/"):
                return redirect(next_url)
            if user_obj.role == 'salesman':
                return redirect(url_for("pos"))
            return redirect(url_for("dashboard"))
        return render_template(
            "login.html",
            error="Invalid username or password.",
        )
    return render_template("login.html")


@app.route("/logout")
def logout():
    logout_user()
    return redirect(url_for("login"))


import traceback

@app.errorhandler(Exception)
def handle_exception(e):
    # pass through HTTP errors
    if isinstance(e, HTTPException):
        return e
    # now you're handling non-HTTP exceptions only
    tb = traceback.format_exc()
    return f"<h1>Internal Server Error</h1><pre>{tb}</pre>", 500

@app.route("/dashboard")
@admin_required
def dashboard():
    conn = get_connection()
    try:
        # Get today's sales
        today = date.today().isoformat()
        daily_revenue_row = conn.execute(
            'SELECT COALESCE(SUM(grand_total), 0) as total_revenue FROM sales WHERE invoice_date = ?', 
            (today,)
        ).fetchone()
        daily_cost_row = conn.execute(
            '''SELECT COALESCE(SUM(si.qty * COALESCE(si.packing_multiplier, 1.0) * si.cost_price), 0) as total_cost 
               FROM sale_items si 
               JOIN sales s ON si.sale_id = s.id 
               WHERE s.invoice_date = ?''', 
            (today,)
        ).fetchone()
        
        daily_revenue = float(daily_revenue_row["total_revenue"] or 0)
        daily_cost = float(daily_cost_row["total_cost"] or 0)
        daily_profit = daily_revenue - daily_cost
        
        # Get monthly revenue and cost
        now = date.today()
        current_month = now.month
        current_year = now.year
        monthly_revenue_row = conn.execute(
            "SELECT COALESCE(SUM(grand_total), 0) as total_revenue FROM sales WHERE strftime('%m', invoice_date) = ? AND strftime('%Y', invoice_date) = ?",
            (f"{current_month:02d}", str(current_year))
        ).fetchone()
        monthly_cost_row = conn.execute(
            '''SELECT COALESCE(SUM(si.qty * COALESCE(si.packing_multiplier, 1.0) * si.cost_price), 0) as total_cost 
               FROM sale_items si 
               JOIN sales s ON si.sale_id = s.id 
               WHERE strftime('%m', s.invoice_date) = ? AND strftime('%Y', s.invoice_date) = ?''',
            (f"{current_month:02d}", str(current_year))
        ).fetchone()
        
        monthly_revenue = float(monthly_revenue_row["total_revenue"] or 0)
        monthly_cost = float(monthly_cost_row["total_cost"] or 0)
        monthly_profit = monthly_revenue - monthly_cost
        monthly_margin = round((monthly_profit / monthly_revenue * 100), 2) if monthly_revenue > 0 else 0
        
        # Get recent sales (last 5)
        recent_sales_rows = conn.execute(
            """
            SELECT
                s.id,
                s.invoice_number,
                s.invoice_date,
                c.name AS customer_name,
                s.grand_total,
                s.payment_type,
                s.status,
                (SELECT COALESCE(SUM(si.qty * COALESCE(si.packing_multiplier, 1.0) * si.cost_price), 0) FROM sale_items si WHERE si.sale_id = s.id) as total_cost
            FROM sales s
            LEFT JOIN customers c ON c.id = s.customer_id
            ORDER BY s.id DESC
            LIMIT 5
            """
        ).fetchall()
        recent_sales = []
        for r in recent_sales_rows:
            d = dict(r)
            rev = float(d["grand_total"] or 0)
            cost = float(d["total_cost"] or 0)
            d["profit_margin"] = round(((rev - cost) / rev * 100), 2) if rev > 0 else 0
            d["profit_amount"] = round(rev - cost, 2)
            recent_sales.append(d)

        # Get upcoming/overdue payments (limit 10)
        upcoming_payments_rows = conn.execute(
            """
            SELECT
                s.id,
                s.invoice_number,
                s.invoice_date,
                s.due_date,
                c.name AS customer_name,
                c.phone AS customer_phone,
                s.remaining_amount
            FROM sales s
            LEFT JOIN customers c ON c.id = s.customer_id
            WHERE s.remaining_amount > 0
              AND s.due_date IS NOT NULL
              AND s.due_date != ''
            ORDER BY s.due_date ASC
            LIMIT 10
            """
        ).fetchall()
        upcoming_payments = [dict(r) for r in upcoming_payments_rows]
        
        # Get daily sales for the last 30 days
        thirty_days_ago = (date.today() - timedelta(days=30)).isoformat()
        daily_sales_rows = conn.execute(
            """
            SELECT invoice_date, SUM(grand_total) as daily_total
            FROM sales
            WHERE invoice_date >= ?
            GROUP BY invoice_date
            ORDER BY invoice_date ASC
            """,
            (thirty_days_ago,)
        ).fetchall()
        
        daily_sales_labels = [row["invoice_date"] for row in daily_sales_rows]
        daily_sales_data = [row["daily_total"] for row in daily_sales_rows]
        
    finally:
        conn.close()
    
    return render_template(
        "dashboard.html",
        monthly_profit=monthly_profit,
        monthly_margin=monthly_margin,
        daily_revenue=daily_revenue,
        daily_profit=daily_profit,
        monthly_revenue=monthly_revenue,
        recent_sales=recent_sales,
        upcoming_payments=upcoming_payments,
        daily_sales_labels=daily_sales_labels,
        daily_sales_data=daily_sales_data,
    )


@app.route("/inventory")
@admin_required
def inventory():
    brand_filter = request.args.get("brand", "").strip()
    date_from = request.args.get("date_from", "").strip()
    date_to = request.args.get("date_to", "").strip()

    conn = get_connection()
    try:
        query = """
            SELECT
                p.id,
                p.name,
                p.brand,
                p.unit,
                p.cost_price,
                p.selling_price,
                p.stock_quantity,
                p.image_url,
                p.is_public,
                p.category_id,
                p.created_at,
                p.supplier_id,
                p.is_open,
                c.name AS category_name
            FROM products p
            LEFT JOIN categories c ON p.category_id = c.id

            WHERE 1=1
        """
        params = []
        
        if brand_filter:
            query += " AND p.brand = ?"
            params.append(brand_filter)
        if date_from:
            query += " AND date(p.created_at) >= ?"
            params.append(date_from)
        if date_to:
            query += " AND date(p.created_at) <= ?"
            params.append(date_to)
            
        query += " ORDER BY p.name COLLATE NOCASE"
        cur = conn.execute(query, params)
        products = [dict(row) for row in cur.fetchall()]

        cur = conn.execute("SELECT COUNT(*) AS total_products FROM products")
        total_products = int(cur.fetchone()["total_products"] or 0)

        cur = conn.execute(
            """
            SELECT COALESCE(SUM(COALESCE(cost_price, 0) * COALESCE(stock_quantity, 0)), 0) AS total_stock_value
            FROM products
            """
        )
        total_stock_value = float(cur.fetchone()["total_stock_value"] or 0)

        cur = conn.execute(
            """
            SELECT
                COALESCE(SUM(CASE WHEN COALESCE(stock_quantity, 0) < 5 THEN 1 ELSE 0 END), 0) AS low_stock_count
            FROM products
            """
        )
        low_stock_count = int(cur.fetchone()["low_stock_count"] or 0)

        cur = conn.execute("SELECT id, name FROM categories ORDER BY name COLLATE NOCASE")
        categories = [dict(row) for row in cur.fetchall()]

        cur = conn.execute("SELECT id, name FROM suppliers ORDER BY name COLLATE NOCASE")
        suppliers = [dict(row) for row in cur.fetchall()]
    finally:
        conn.close()

    return render_template(
        "inventory.html",
        products=products,
        categories=categories,
        suppliers=suppliers,
        total_products=total_products,
        total_stock_value=total_stock_value,
        low_stock_count=low_stock_count,
    )


@app.route("/inventory/download_csv")
@admin_required
def inventory_download_csv():
    brand = request.args.get("brand", "").strip()
    date_from = request.args.get("date_from", "").strip()
    date_to = request.args.get("date_to", "").strip()
    
    conn = get_connection()
    try:
        query = """
            SELECT
                p.id,
                p.name,
                p.brand,
                p.unit,
                p.cost_price,
                p.selling_price,
                p.stock_quantity,
                p.created_at,
                c.name AS category_name
            FROM products p
            LEFT JOIN categories c ON p.category_id = c.id
            WHERE 1=1
        """
        params = []
        if brand:
            query += " AND p.brand = ?"
            params.append(brand)
        if date_from:
            query += " AND date(p.created_at) >= ?"
            params.append(date_from)
        if date_to:
            query += " AND date(p.created_at) <= ?"
            params.append(date_to)
            
        query += " ORDER BY p.name COLLATE NOCASE"
        cur = conn.execute(query, params)
        products = [dict(row) for row in cur.fetchall()]
    finally:
        conn.close()

    import io
    import csv
    
    output = io.StringIO()
    writer = csv.writer(output)
    
    # Write header
    writer.writerow([
        "ID", "Date Added", "Product Name", "Brand", "Category", 
        "Cost Price", "Selling Price", "Stock Quantity", "Stock Value"
    ])
    
    # Write rows
    total_qty = 0
    total_value = 0.0

    for p in products:
        stock_qty = p["stock_quantity"] if p["stock_quantity"] is not None else 0
        stock_val = float(stock_qty) * float(p["cost_price"] or 0)
        total_qty += stock_qty
        total_value += stock_val
        
        writer.writerow([
            p["id"],
            str(p["created_at"] or "")[:10],
            p["name"],
            p["brand"] or "",
            p["category_name"] or "",
            f"{p['cost_price']:.2f}" if p['cost_price'] is not None else "0.00",
            f"{p['selling_price']:.2f}" if p['selling_price'] is not None else "0.00",
            stock_qty,
            f"{stock_val:.2f}"
        ])
    
    # Write totals row
    writer.writerow([
        "", "", "TOTALS", "", "", "", "", total_qty, f"{total_value:.2f}"
    ])
    
    from datetime import date
    today_str = date.today().strftime("%Y-%m-%d")
    filename = f"inventory_{brand}_{today_str}.csv" if brand else f"inventory_all_{today_str}.csv"
    response = Response(output.getvalue(), mimetype="text/csv")
    response.headers["Content-Disposition"] = f"attachment; filename={filename}"
    return response




@app.route("/inventory/add", methods=["POST"])
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
        cur = conn.execute("SELECT id, stock_quantity FROM products WHERE LOWER(name) = LOWER(?)", (product_name,))
        existing = cur.fetchone()
        
        if existing:
            product_id = existing["id"]
            old_stock = float(existing["stock_quantity"] or 0)
            new_stock = float(stock_quantity)
            
            update_query = """
                UPDATE products
                SET category_id = ?, brand = ?, unit = ?, cost_price = ?, selling_price = ?, stock_quantity = ?, supplier_id = ?, is_open = ?
            """
            params = [category_id, brand or None, unit, cost_price, selling_price, new_stock, supplier_id, is_open]
            
            if created_at:
                update_query += ", created_at = ?"
                params.append(created_at)
                
            if image_url:
                update_query += ", image_url = ?"
                params.append(image_url)
            update_query += " WHERE id = ?"
            params.append(product_id)
            
            conn.execute(update_query, params)
            
            if new_stock != old_stock:
                diff = new_stock - old_stock
                t_type = 'IN' if diff > 0 else 'ADJUSTMENT'
                conn.execute("""
                    INSERT INTO inventory_history (product_id, transaction_type, quantity_change, previous_stock, new_stock, reference, supplier_id)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                """, (product_id, t_type, diff, old_stock, new_stock, 'Manual Edit (Add Product)', supplier_id))
        else:
            if created_at:
                cur = conn.execute(
                    """
                    INSERT INTO products
                        (name, category_id, brand, unit, cost_price, selling_price, stock_quantity, image_url, created_at, is_public, supplier_id, is_open)
                    VALUES
                        (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (product_name, category_id, brand or None, unit, cost_price, selling_price, stock_quantity, image_url, created_at, is_public, supplier_id, is_open),
                )
            else:
                cur = conn.execute(
                    """
                    INSERT INTO products
                        (name, category_id, brand, unit, cost_price, selling_price, stock_quantity, image_url, is_public, supplier_id, is_open)
                    VALUES
                        (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (product_name, category_id, brand or None, unit, cost_price, selling_price, stock_quantity, image_url, is_public, supplier_id, is_open),
                )
            product_id = int(cur.lastrowid)
            
            if stock_quantity != 0:
                conn.execute("""
                    INSERT INTO inventory_history (product_id, transaction_type, quantity_change, previous_stock, new_stock, reference, supplier_id)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                """, (product_id, 'IN', stock_quantity, 0, stock_quantity, 'Initial Stock', supplier_id))

        # Keep brands table in sync for the Brand dropdown.
        if brand:
            conn.execute("INSERT OR IGNORE INTO brands (name) VALUES (?)", (brand,))

        conn.commit()
    finally:
        conn.close()

    return redirect(url_for("inventory"))


@app.route("/inventory/edit/<int:product_id>", methods=["POST"])
@admin_required
def inventory_edit(product_id: int):
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

    remove_image = request.form.get("remove_image") == "1"

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
        
        cur = conn.execute("SELECT stock_quantity FROM products WHERE id = ?", (product_id,))
        old_stock_row = cur.fetchone()
        old_stock = float(old_stock_row["stock_quantity"] or 0) if old_stock_row else 0
        new_stock = float(stock_quantity)
        
        # If user uploaded a new image, use it. Else if they clicked remove, set it to NULL.
        # Otherwise, keep existing image_url.
        update_query = """
            UPDATE products
            SET name = ?, brand = ?, category_id = ?, unit = ?, cost_price = ?, selling_price = ?, stock_quantity = ?, is_public = ?, supplier_id = ?, is_open = ?
        """
        params = [product_name, brand, category_id, unit, cost_price, selling_price, stock_quantity, is_public, supplier_id, is_open]
        
        if created_at:
            update_query += ", created_at = ?"
            params.append(created_at)

        if image_url:
            update_query += ", image_url = ?"
            params.append(image_url)
        elif remove_image:
            update_query += ", image_url = NULL"
            
        update_query += " WHERE id = ?"
        params.append(product_id)
        
        conn.execute(update_query, params)
        
        if new_stock != old_stock:
            diff = new_stock - old_stock
            t_type = 'IN' if diff > 0 else 'ADJUSTMENT'
            conn.execute("""
                INSERT INTO inventory_history (product_id, transaction_type, quantity_change, previous_stock, new_stock, reference, supplier_id)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (product_id, t_type, diff, old_stock, new_stock, 'Manual Edit (Edit Product)', supplier_id))


        # Keep brands table in sync for the Brand dropdown.
        if brand:
            conn.execute("INSERT OR IGNORE INTO brands (name) VALUES (?)", (brand,))

        conn.commit()
    finally:
        conn.close()

    return redirect(url_for("inventory"))


@app.route("/inventory/delete/<int:product_id>", methods=["POST"])
@admin_required
def inventory_delete(product_id: int):
    is_ajax = request.headers.get("X-Requested-With") == "fetch"

    conn = get_connection()
    ok = False
    error = None
    try:
        # Remove references to avoid FOREIGN KEY constraint error
        conn.execute("UPDATE sale_items SET product_id = NULL WHERE product_id = ?", (product_id,))
        conn.execute("DELETE FROM inventory_history WHERE product_id = ?", (product_id,))
        
        cur = conn.execute("DELETE FROM products WHERE id = ?", (product_id,))
        conn.commit()
        ok = cur.rowcount > 0
        if not ok:
            error = "Product not found."
    except sqlite3.IntegrityError as e:
        ok = False
        error = str(e)
    finally:
        conn.close()

    if is_ajax:
        if ok:
            return jsonify({"ok": True})
        return jsonify({"ok": False, "error": error or "Delete failed."}), 400

    return redirect(url_for("inventory"))


@app.route("/api/inventory_history/<int:product_id>", methods=["GET"])
@login_required
def api_inventory_history(product_id):
    conn = get_connection()
    try:
        cur = conn.execute(
            """
            SELECT 
                h.transaction_type, 
                h.quantity_change, 
                h.previous_stock, 
                h.new_stock, 
                h.reference, 
                h.created_at,
                s.name as supplier_name
            FROM inventory_history h
            LEFT JOIN suppliers s ON h.supplier_id = s.id
            WHERE h.product_id = ?
            ORDER BY h.created_at DESC
            """,
            (product_id,)
        )
        history = [dict(row) for row in cur.fetchall()]
        return jsonify({"ok": True, "history": history})
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500
    finally:
        conn.close()


@app.route("/categories/add", methods=["POST"])
@admin_required
def categories_add():
    is_ajax = request.headers.get("X-Requested-With") == "fetch"

    data = request.get_json(silent=True) or {}
    if not data:
        data = request.form or {}

    name = (data.get("name") or "").strip()
    if not name:
        if is_ajax:
            return jsonify({"ok": False, "error": "Category name is required."}), 400
        return redirect(url_for("inventory"))

    conn = get_connection()
    try:
        try:
            cur = conn.execute("INSERT INTO categories (name) VALUES (?)", (name,))
            conn.commit()
            category_id = int(cur.lastrowid)
        except sqlite3.IntegrityError:
            cur = conn.execute("SELECT id, name FROM categories WHERE name = ?", (name,))
            row = cur.fetchone()
            category_id = int(row["id"]) if row else None
            if not category_id:
                raise
        category_name = name
        return jsonify({"id": category_id, "name": category_name})
    finally:
        conn.close()


@app.route("/categories", methods=["GET"])
@login_required
def categories_list():
    conn = get_connection()
    try:
        cur = conn.execute("SELECT id, name FROM categories ORDER BY name COLLATE NOCASE")
        categories = [dict(row) for row in cur.fetchall()]
    finally:
        conn.close()
    return jsonify(categories)


@app.route("/categories/delete/<int:category_id>", methods=["POST"])
@admin_required
def categories_delete(category_id: int):
    is_ajax = request.headers.get("X-Requested-With") == "fetch"
    conn = get_connection()
    try:
        cur = conn.execute("SELECT COUNT(*) AS c FROM products WHERE category_id = ?", (category_id,))
        used_count = int(cur.fetchone()["c"] or 0)
        if used_count > 0:
            msg = "Category cannot be deleted because it is used by one or more products."
            if is_ajax:
                return jsonify({"ok": False, "error": msg}), 409
            return redirect(url_for("inventory"))

        cur2 = conn.execute("DELETE FROM categories WHERE id = ?", (category_id,))
        conn.commit()
        ok = cur2.rowcount > 0
        if ok:
            return jsonify({"ok": True}) if is_ajax else redirect(url_for("inventory"))
        msg = "Category not found."
        return (
            (jsonify({"ok": False, "error": msg}), 400)
            if is_ajax
            else redirect(url_for("inventory"))
        )
    finally:
        conn.close()


@app.route("/categories/edit/<int:category_id>", methods=["POST"])
@admin_required
def categories_edit(category_id: int):
    is_ajax = request.headers.get("X-Requested-With") == "fetch"
    data = request.get_json(silent=True) or {}
    if not data:
        data = request.form or {}

    name = (data.get("name") or "").strip()
    if not name:
        if is_ajax:
            return jsonify({"ok": False, "error": "Category name is required."}), 400
        return redirect(url_for("inventory"))

    conn = get_connection()
    try:
        try:
            cur = conn.execute(
                "UPDATE categories SET name = ? WHERE id = ?",
                (name, category_id),
            )
            conn.commit()
            if cur.rowcount == 0:
                if is_ajax:
                    return jsonify({"ok": False, "error": "Category not found."}), 404
                return redirect(url_for("inventory"))
        except sqlite3.IntegrityError:
            # Unique constraint on categories.name
            if is_ajax:
                return jsonify({"ok": False, "error": "Category name already exists."}), 409
            return redirect(url_for("inventory"))
    finally:
        conn.close()

    if is_ajax:
        return jsonify({"ok": True, "id": category_id, "name": name})
    return redirect(url_for("inventory"))


@app.route("/brands/list", methods=["GET"])
@login_required
def brands_list():
    """
    Returns all brands as JSON [{id, name}].
    If brands table is empty (fresh DB), derive initial values from products.brand.
    """
    conn = get_connection()
    try:
        # Backfill brands from existing products (idempotent).
        conn.execute(
            """
            INSERT OR IGNORE INTO brands (name)
            SELECT DISTINCT TRIM(brand)
            FROM products
            WHERE brand IS NOT NULL AND TRIM(brand) != ''
            """
        )
        conn.commit()

        cur = conn.execute(
            "SELECT id, name FROM brands ORDER BY name COLLATE NOCASE"
        )
        return jsonify([{"id": int(r["id"]), "name": r["name"]} for r in cur.fetchall()])
    finally:
        conn.close()


@app.route("/brands/add", methods=["POST"])
@admin_required
def brands_add():
    is_json = request.is_json
    data = request.get_json(silent=True) if is_json else {}
    if not data:
        data = request.form or {}

    name = (data.get("name") or "").strip()
    if not name:
        return jsonify({"ok": False, "error": "Brand name is required."}), 400

    conn = get_connection()
    try:
        conn.execute("INSERT OR IGNORE INTO brands (name) VALUES (?)", (name,))
        conn.commit()

        cur = conn.execute("SELECT id, name FROM brands WHERE name = ?", (name,))
        row = cur.fetchone()
        if row is None:
            return jsonify({"ok": False, "error": "Failed to create brand."}), 500

        return jsonify({"ok": True, "id": int(row["id"]), "name": row["name"]})
    finally:
        conn.close()



@app.route("/suppliers", methods=["GET"])
@admin_required
def suppliers_page():
    conn = get_connection()
    try:
        cur_suppliers = conn.execute("""
            SELECT s.*, COUNT(p.id) as products_count,
                   (SELECT COALESCE(SUM(remaining_amount), 0) FROM purchases WHERE supplier_id = s.id) as total_balance,
                   (SELECT COALESCE(SUM(amount_paid), 0) FROM purchases WHERE supplier_id = s.id) as total_paid
            FROM suppliers s
            LEFT JOIN products p ON s.id = p.supplier_id
            GROUP BY s.id
            ORDER BY s.name COLLATE NOCASE
        """)
        suppliers = [dict(r) for r in cur_suppliers.fetchall()]
        
        cur_brands = conn.execute("""
            SELECT b.*, COUNT(p.id) as products_count
            FROM brands b
            LEFT JOIN products p ON b.name = p.brand
            GROUP BY b.id
            ORDER BY b.name COLLATE NOCASE
        """)
        brands = [dict(r) for r in cur_brands.fetchall()]
        
        return render_template("suppliers.html", suppliers=suppliers, brands=brands)
    finally:
        conn.close()

@app.route("/suppliers/add", methods=["POST"])
@admin_required
def suppliers_add():
    name = request.form.get("name", "").strip()
    contact_name = request.form.get("contact_name", "").strip()
    phone = request.form.get("phone", "").strip()
    address = request.form.get("address", "").strip()
    
    if not name:
        return "Supplier Business Name is required.", 400
        
    conn = get_connection()
    try:
        conn.execute("INSERT INTO suppliers (name, contact_name, phone, address) VALUES (?, ?, ?, ?)", (name, contact_name, phone, address))
        conn.commit()
    finally:
        conn.close()
    return redirect(url_for("suppliers_page"))

@app.route("/suppliers/edit/<int:supplier_id>", methods=["POST"])
@admin_required
def suppliers_edit(supplier_id):
    name = request.form.get("name", "").strip()
    contact_name = request.form.get("contact_name", "").strip()
    phone = request.form.get("phone", "").strip()
    address = request.form.get("address", "").strip()
    
    if not name:
        return "Supplier Business Name is required.", 400
        
    conn = get_connection()
    try:
        conn.execute("UPDATE suppliers SET name = ?, contact_name = ?, phone = ?, address = ? WHERE id = ?", (name, contact_name, phone, address, supplier_id))
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

@app.route("/suppliers/<int:supplier_id>/history", methods=["GET"])
@admin_required
def supplier_history(supplier_id):
    conn = get_connection()
    try:
        rows = conn.execute(
            '''
            SELECT
                date(ih.created_at) as addition_date,
                p.name AS product_name,
                COALESCE(SUM(ih.quantity_change), 0) AS total_added,
                COALESCE(SUM(ih.quantity_change * p.cost_price), 0) AS total_value
            FROM inventory_history ih
            JOIN products p ON p.id = ih.product_id
            WHERE p.supplier_id = ? AND ih.transaction_type = 'IN'
              AND ih.reference IN ('Initial Stock', 'Initial Stock (Legacy)', 'Manual Edit', 'Manual Edit (Edit Product)')
            GROUP BY date(ih.created_at), p.id
            ORDER BY addition_date DESC, p.name ASC
            ''', (supplier_id,)
        ).fetchall()
        
        result = []
        for r in rows:
            result.append({
                "addition_date": r["addition_date"],
                "product_name": r["product_name"],
                "total_added": float(r["total_added"] or 0),
                "total_value": float(r["total_value"] or 0)
            })
        return jsonify(result)
    finally:
        conn.close()

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

@app.route("/products/list", methods=["GET"])
@login_required
def products_list():
    conn = get_connection()
    try:
        cur = conn.execute(
            """
            SELECT
                p.id AS id,
                p.name AS name,
                b.id AS brand_id,
                p.brand AS brand_name,
                p.category_id AS category_id,
                p.unit AS unit,
                p.cost_price AS cost_price,
                p.selling_price AS selling_price,
                p.stock_quantity AS stock_quantity,
                p.image_url AS image_url
            FROM products p
            LEFT JOIN brands b
                ON LOWER(b.name) = LOWER(p.brand)
            GROUP BY p.id
            ORDER BY p.name COLLATE NOCASE, p.id ASC
            """
        )
        rows = cur.fetchall()
        return jsonify(
            [
                {
                    "id": int(r["id"]),
                    "name": r["name"],
                    "brand_id": int(r["brand_id"]) if r["brand_id"] is not None else None,
                    "brand_name": r["brand_name"],
                    "category_id": int(r["category_id"]) if r["category_id"] is not None else None,
                    "unit": r["unit"] or "Each",
                    "cost_price": float(r["cost_price"] or 0),
                    "selling_price": float(r["selling_price"] or 0),
                    "stock_quantity": int(r["stock_quantity"] or 0),
                    "image_url": r["image_url"],
                }
                for r in rows
            ]
        )
    finally:
        conn.close()


@app.route("/brands/search", methods=["GET"])
@login_required
def brands_search():
    q = (request.args.get("q") or "").strip()
    if not q:
        return jsonify([])

    like = f"%{q}%"
    conn = get_connection()
    try:
        rows = conn.execute(
            """
            SELECT DISTINCT brand
            FROM products
            WHERE brand IS NOT NULL AND TRIM(brand) != '' AND brand LIKE ?
            ORDER BY brand COLLATE NOCASE
            LIMIT 15
            """,
            (like,),
        ).fetchall()
        return jsonify([r["brand"] for r in rows if r["brand"]])
    finally:
        conn.close()


@app.route("/backup/download")
@admin_required
def backup_download():
    import io
    import csv
    import zipfile
    from flask import send_file
    from datetime import date
    
    conn = get_connection()
    try:
        tables = ["users", "customers", "categories", "brands", "products", "sales", "sale_items"]
        
        memory_file = io.BytesIO()
        with zipfile.ZipFile(memory_file, 'w', zipfile.ZIP_DEFLATED) as zf:
            # Add database.db
            zf.write(DB_PATH, arcname='database.db')
            
            # Add all uploaded product images
            upload_folder = os.path.join(app.root_path, "static", "uploads", "products")
            if os.path.exists(upload_folder):
                for root, _, files in os.walk(upload_folder):
                    for file in files:
                        full_path = os.path.join(root, file)
                        rel_path = os.path.relpath(full_path, app.root_path)
                        zf.write(full_path, arcname=rel_path)
            
            # Export each table to CSV
            for table in tables:
                rows = conn.execute(f"SELECT * FROM {table}").fetchall()
                if rows:
                    csv_io = io.StringIO()
                    writer = csv.writer(csv_io)
                    writer.writerow(rows[0].keys())
                    for row in rows:
                        writer.writerow(tuple(row))
                    zf.writestr(f"{table}.csv", csv_io.getvalue())
        
        memory_file.seek(0)
        return send_file(
            memory_file,
            mimetype="application/zip",
            as_attachment=True,
            download_name=f"AK_Distributors_Backup_{date.today().isoformat()}.zip"
        )
    finally:
        conn.close()


@app.route("/customers")
@admin_required
def customers():
    conn = get_connection()
    try:
        cur = conn.execute(
            """
            SELECT
                id,
                name,
                bill_address,
                ship_address,
                area,
                state,
                phone,
                email,
                terms,
                created_at
            FROM customers
            ORDER BY created_at DESC, id DESC
            """
        )
        customers_list = [dict(row) for row in cur.fetchall()]

        cur = conn.execute("SELECT COUNT(*) AS c FROM customers")
        total_customers = int(cur.fetchone()["c"] or 0)

        cur = conn.execute(
            """
            SELECT COUNT(DISTINCT NULLIF(TRIM(area), '')) AS c
            FROM customers
            """
        )
        areas_covered = int(cur.fetchone()["c"] or 0)
    finally:
        conn.close()

    error = request.args.get("error")
    return render_template(
        "customers.html",
        customers=customers_list,
        total_customers=total_customers,
        areas_covered=areas_covered,
        error=error,
    )


@app.route("/customers/add", methods=["POST"])
@admin_required
def customers_add():
    full_name = (request.form.get("full_name") or "").strip()
    bill_address = (request.form.get("bill_address") or "").strip()
    phone = (request.form.get("phone") or "").strip()
    
    # Server-side validation for mandatory fields
    if not full_name:
        return redirect(url_for("customers", error="Full Name is required."))
    if not bill_address:
        return redirect(url_for("customers", error="Billing Address is required."))
    if not phone:
        return redirect(url_for("customers", error="Phone is required."))

    ship_address = request.form.get("ship_address") or ""
    same_as_billing = request.form.get("same_as_billing") == "on"
    if same_as_billing:
        ship_address = bill_address

    area = (request.form.get("area") or "").strip() or None
    state = (request.form.get("state") or "").strip() or None
    email = (request.form.get("email") or "").strip() or None
    terms_raw = (request.form.get("terms") or "").strip()
    terms = terms_raw if terms_raw else None

    conn = get_connection()
    try:
        conn.execute(
            """
            INSERT INTO customers
                (name, bill_address, ship_address, area, state, phone, email, terms)
            VALUES
                (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (full_name, bill_address or None, ship_address or None, area, state, phone, email, terms),
        )
        conn.commit()
    finally:
        conn.close()

    return redirect(url_for("customers"))


@app.route("/customers/edit/<int:customer_id>", methods=["POST"])
@admin_required
def customers_edit(customer_id: int):
    full_name = (request.form.get("full_name") or "").strip()
    bill_address = (request.form.get("bill_address") or "").strip()
    phone = (request.form.get("phone") or "").strip()
    
    # Server-side validation for mandatory fields
    if not full_name:
        return redirect(url_for("customers", error="Full Name is required."))
    if not bill_address:
        return redirect(url_for("customers", error="Billing Address is required."))
    if not phone:
        return redirect(url_for("customers", error="Phone is required."))

    ship_address = request.form.get("ship_address") or ""
    same_as_billing = request.form.get("same_as_billing") == "on"
    if same_as_billing:
        ship_address = bill_address

    area = (request.form.get("area") or "").strip() or None
    state = (request.form.get("state") or "").strip() or None
    email = (request.form.get("email") or "").strip() or None
    terms_raw = (request.form.get("terms") or "").strip()
    terms = terms_raw if terms_raw else None

    conn = get_connection()
    try:
        conn.execute(
            """
            UPDATE customers
            SET
                name = ?,
                bill_address = ?,
                ship_address = ?,
                area = ?,
                state = ?,
                phone = ?,
                email = ?,
                terms = ?
            WHERE id = ?
            """,
            (full_name, bill_address or None, ship_address or None, area, state, phone, email, terms, customer_id),
        )
        conn.commit()
    finally:
        conn.close()

    return redirect(url_for("customers"))


@app.route("/customers/delete/<int:customer_id>", methods=["POST"])
@admin_required
def customers_delete(customer_id: int):
    conn = get_connection()
    try:
        # Keep sales history rows, but detach them from the deleted customer.
        conn.execute("UPDATE sales SET customer_id = NULL WHERE customer_id = ?", (customer_id,))
        conn.execute("DELETE FROM customers WHERE id = ?", (customer_id,))
        conn.commit()
    finally:
        conn.close()

    return redirect(url_for("customers"))

@app.route("/customers/list", methods=["GET"])
@login_required
def customers_list():
    conn = get_connection()
    try:
        cur = conn.execute("SELECT * FROM customers ORDER BY name")
        cust_list = [dict(r) for r in cur.fetchall()]
        return jsonify(cust_list)
    finally:
        conn.close()


@app.route("/customers/<int:customer_id>/history", methods=["GET"])
@admin_required
def customers_history(customer_id: int):
    conn = get_connection()
    try:
        cur = conn.execute(
            """
            SELECT 
              s.invoice_number,
              s.invoice_date,
              s.grand_total,
              s.payment_type,
              s.status,
              s.amount_paid,
              s.remaining_amount,
              COUNT(si.id) as item_count
            FROM sales s
            LEFT JOIN sale_items si ON si.sale_id = s.id
            WHERE s.customer_id = ?
            GROUP BY s.id
            ORDER BY s.invoice_date DESC
            """,
            (customer_id,),
        )
        rows = cur.fetchall()
        return jsonify([dict(r) for r in rows])
    finally:
        conn.close()


@app.route("/sales")
@admin_required
def sales():
    conn = get_connection()
    try:
        customers = conn.execute(
            """
            SELECT id, name, terms
            FROM customers
            ORDER BY name COLLATE NOCASE
            """
        ).fetchall()
        customers_list = [dict(r) for r in customers]
        
        users_rows = conn.execute("SELECT id, username, role FROM users ORDER BY username").fetchall()
        users_list = [dict(r) for r in users_rows]

        recent_sales_rows = conn.execute(
            """
            SELECT
                s.id,
                s.invoice_number,
                s.invoice_date,
                c.name AS customer_name,
                COUNT(si.id) AS item_count,
                COALESCE(s.subtotal, 0) AS subtotal,
                COALESCE(s.discount_amount, 0) AS discount_amount,
                COALESCE(s.grand_total, 0) AS grand_total,
                s.payment_type,
                s.status,
                COALESCE(s.amount_paid, 0) AS amount_paid,
                COALESCE(s.remaining_amount, 0) AS remaining_amount,
                COALESCE(SUM(si.qty * COALESCE(si.packing_multiplier, 1.0) * si.cost_price), 0) AS total_cost,
                u.username AS salesman_name
            FROM sales s
            LEFT JOIN customers c ON c.id = s.customer_id
            LEFT JOIN sale_items si ON si.sale_id = s.id
            LEFT JOIN users u ON u.id = s.salesman_id
            GROUP BY s.id
            ORDER BY s.invoice_date DESC, s.id DESC
            LIMIT 10
            """
        ).fetchall()
        recent_sales = []
        for r in recent_sales_rows:
            d = dict(r)
            rev = float(d["grand_total"] or 0)
            cost = float(d["total_cost"] or 0)
            d["profit_margin"] = round(((rev - cost) / rev * 100), 2) if rev > 0 else 0
            d["profit_amount"] = round(rev - cost, 2)
            recent_sales.append(d)
    finally:
        conn.close()

    return render_template(
        "sales.html",
        customers=customers_list,
        recent_sales=recent_sales,
        next_invoice_number=get_next_invoice_number(),
        today=date.today().isoformat(),
        all_users=users_list,
    )


@app.route("/sales/next-invoice", methods=["GET"])
@login_required
def sales_next_invoice():
    return jsonify({"invoice_number": get_next_invoice_number()})


@app.route("/products/search", methods=["GET"])
@login_required
def products_search():
    q = (request.args.get("q") or "").strip()
    like = f"%{q}%"
    conn = get_connection()
    try:
        if not q:
            cur = conn.execute(
                """
                SELECT
                    id,
                    name,
                    brand,
                    selling_price,
                    cost_price,
                    unit,
                    stock_quantity,
                    is_open
                FROM products
                ORDER BY name COLLATE NOCASE
                LIMIT 20
                """
            )
        else:
            cur = conn.execute(
                """
                SELECT
                    id,
                    name,
                    brand,
                    selling_price,
                    cost_price,
                    unit,
                    stock_quantity,
                    is_open
                FROM products
                WHERE name LIKE ? OR brand LIKE ?
                ORDER BY name COLLATE NOCASE
                LIMIT 15
                """,
                (like, like),
            )
        results = []
        for r in cur.fetchall():
            results.append(
                {
                    "id": r["id"],
                    "name": r["name"],
                    "brand": r["brand"],
                    "selling_price": r["selling_price"],
                    "cost_price": r["cost_price"],
                    "unit": r["unit"],
                    "stock_quantity": r["stock_quantity"],
                    "is_open": r["is_open"],
                }
            )
        return jsonify(results)
    finally:
        conn.close()




@app.route("/sales/data", methods=["GET"])
@login_required
def sales_data():
    date_from = (request.args.get("date_from") or "").strip()
    date_to = (request.args.get("date_to") or "").strip()
    customer_id = (request.args.get("customer_id") or "").strip()
    payment_type = (request.args.get("payment_type") or "").strip()
    salesman_id = (request.args.get("salesman_id") or "").strip()
    salesman_name_filter = (request.args.get("salesman_name") or "").strip()
    search = (request.args.get("search") or "").strip()

    conditions = []
    params = []

    if date_from:
        conditions.append("s.invoice_date >= ?")
        params.append(date_from)
    if date_to:
        conditions.append("s.invoice_date <= ?")
        params.append(date_to)
    if customer_id and customer_id not in ("all", "0"):
        try:
            customer_id_int = int(customer_id)
            conditions.append("s.customer_id = ?")
            params.append(customer_id_int)
        except ValueError:
            pass
            
    if salesman_name_filter:
        conditions.append("LOWER(COALESCE(u.username, 'admin')) = ?")
        params.append(salesman_name_filter.lower())
    else:
        if salesman_id and salesman_id not in ("all", "0"):
            try:
                salesman_id_int = int(salesman_id)
                conditions.append("s.salesman_id = ?")
                params.append(salesman_id_int)
            except ValueError:
                pass
        elif salesman_id == "0":
            conditions.append("s.salesman_id IS NULL")
        
    if payment_type and payment_type not in ("all", ""):
        conditions.append("s.payment_type = ?")
        params.append(payment_type)

    if search:
        search_term = f"%{search.lower()}%"
        conditions.append("(LOWER(s.invoice_number) LIKE ? OR LOWER(c.name) LIKE ?)")
        params.extend([search_term, search_term])

    where_sql = ""
    if conditions:
        where_sql = "WHERE " + " AND ".join(conditions)

    conn = get_connection()
    try:
        cur = conn.execute(
            f"""
            SELECT
                s.id,
                s.invoice_number,
                s.invoice_date,
                s.customer_id,
                s.payment_type,
                s.subtotal,
                s.discount_amount,
                s.grand_total,
                s.status,
                s.notes,
                s.amount_paid,
                s.remaining_amount,
                c.name as customer_name,
                c.terms as customer_terms,
                u.username as salesman_name,
                (SELECT COALESCE(SUM(si.qty * COALESCE(si.packing_multiplier, 1.0) * si.cost_price), 0) FROM sale_items si WHERE si.sale_id = s.id) as total_cost
            FROM sales s
            LEFT JOIN customers c ON c.id = s.customer_id
            LEFT JOIN users u ON u.id = s.salesman_id
            {where_sql}
            ORDER BY s.id DESC
            """
        , params)
        sales_list = []
        for r in cur.fetchall():
            d = dict(r)
            rev = float(d["grand_total"] or 0)
            cost = float(d["total_cost"] or 0)
            d["profit_margin"] = round(((rev - cost) / rev * 100), 2) if rev > 0 else 0
            d["profit_amount"] = round(rev - cost, 2)
            sales_list.append(d)
        return jsonify(sales_list)
    finally:
        conn.close()


@app.route("/sales/export", methods=["GET"])
@admin_required
def sales_export():
    import csv
    import io
    import datetime

    date_from = (request.args.get("date_from") or "").strip()
    date_to = (request.args.get("date_to") or "").strip()
    customer_id = (request.args.get("customer_id") or "").strip()
    payment_type = (request.args.get("payment_type") or "").strip()
    search = (request.args.get("search") or "").strip()

    conditions = []
    params = []

    if date_from:
        conditions.append("s.invoice_date >= ?")
        params.append(date_from)
    if date_to:
        conditions.append("s.invoice_date <= ?")
        params.append(date_to)
    if customer_id and customer_id not in ("all", "0"):
        try:
            customer_id_int = int(customer_id)
            conditions.append("s.customer_id = ?")
            params.append(customer_id_int)
        except ValueError:
            pass
    if payment_type and payment_type not in ("all", ""):
        conditions.append("s.payment_type = ?")
        params.append(payment_type)

    if search:
        search_term = f"%{search.lower()}%"
        conditions.append("(LOWER(s.invoice_number) LIKE ? OR LOWER(c.name) LIKE ?)")
        params.extend([search_term, search_term])

    where_sql = ""
    if conditions:
        where_sql = "WHERE " + " AND ".join(conditions)

    conn = get_connection()
    try:
        cur = conn.execute(
            f"""
            SELECT
                s.id,
                s.invoice_number,
                s.invoice_date,
                s.customer_id,
                s.payment_type,
                s.subtotal,
                s.discount_amount,
                s.grand_total,
                s.status,
                s.notes,
                s.amount_paid,
                s.remaining_amount,
                c.name as customer_name,
                (SELECT COUNT(si.id) FROM sale_items si WHERE si.sale_id = s.id) as item_count,
                (SELECT COALESCE(SUM(si.qty * COALESCE(si.packing_multiplier, 1.0) * si.cost_price), 0) FROM sale_items si WHERE si.sale_id = s.id) as total_cost
            FROM sales s
            LEFT JOIN customers c ON c.id = s.customer_id
            {where_sql}
            ORDER BY s.id DESC
            """
        , params)
        rows = cur.fetchall()
    finally:
        conn.close()

    headers = [
        "Invoice No", "Date", "Customer", "Items", "Subtotal", "Discount",
        "Grand Total", "Profit Margin", "Profit Amount",
        "Payment Type", "Status", "Amount Paid", "Remaining Balance"
    ]
    
    csv_rows = []
    for r in rows:
        d = dict(r)
        rev = float(d["grand_total"] or 0)
        cost = float(d["total_cost"] or 0)
        margin = round(((rev - cost) / rev * 100), 2) if rev > 0 else 0.0
        profit_amount = round(rev - cost, 2)
        csv_rows.append([
            d["invoice_number"] or "",
            d["invoice_date"] or "",
            d["customer_name"] or "Walk-in",
            str(d["item_count"] or 0),
            f'{float(d["subtotal"] or 0):.2f}',
            f'{float(d["discount_amount"] or 0):.2f}',
            f'{rev:.2f}',
            f'{margin:.2f}%',
            f'{profit_amount:.2f}',
            d["payment_type"] or "",
            str(d["status"]),
            f'{float(d["amount_paid"] or 0):.2f}',
            f'{float(d["remaining_amount"] or 0):.2f}'
        ])

    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(headers)
    writer.writerows(csv_rows)
    csv_bytes = output.getvalue().encode("utf-8")

    year = datetime.datetime.now().year
    resp = Response(csv_bytes, mimetype="text/csv")
    resp.headers["Content-Disposition"] = f'attachment; filename="sales_export_{year}.csv"'
    return resp


@app.route("/sales/new", methods=["POST"])
@admin_required
def sales_new():
    customer_id_raw = (request.form.get("customer_id") or "").strip()
    invoice_date = (request.form.get("invoice_date") or "").strip()
    due_date = (request.form.get("due_date") or "").strip()
    terms = (request.form.get("terms") or "").strip()
    notes = request.form.get("notes") or ""
    invoice_number = (request.form.get("invoice_number") or "").strip()
    payment_type = request.form.get('payment_type', 'cash')
    amount_paid = float(request.form.get('amount_paid', 0) or 0)
    remaining_amount = float(request.form.get('remaining_amount', 0) or 0)
    salesman_id_raw = (request.form.get("salesman_id") or "").strip()
    discount_amount_raw = (request.form.get("discount_amount") or "").strip()
    items_json = request.form.get("items_json") or "[]"
    generate_invoice = "generate_invoice" in request.form

    error = None

    try:
        is_quote = "generate_quote" in request.form
        if is_quote and not customer_id_raw:
            customer_id = None
        else:
            if not customer_id_raw:
                raise ValueError("Customer is required for saving a sale.")
            customer_id = int(customer_id_raw)
        if not invoice_date:
            raise ValueError("Invoice date is required.")
        discount_amount = float(discount_amount_raw) if discount_amount_raw else 0.0
        if discount_amount < 0:
            raise ValueError("Discount cannot be negative.")
        if payment_type not in ("cash", "cheque", "credit"):
            raise ValueError("Invalid payment type.")
        
        # Check if invoice number already exists (for manual invoice numbers)
        if invoice_number:
            conn_check = get_connection()
            try:
                row = conn_check.execute(
                    "SELECT id FROM sales WHERE invoice_number = ?",
                    (invoice_number,),
                ).fetchone()
                if row is not None:
                    raise ValueError(f"Invoice number {invoice_number} already exists.")
            finally:
                conn_check.close()

        if customer_id is not None:
            conn_check = get_connection()
            try:
                row = conn_check.execute(
                    "SELECT id FROM customers WHERE id = ?",
                    (customer_id,),
                ).fetchone()
                if row is None:
                    raise ValueError("Customer not found.")
            finally:
                conn_check.close()
    except ValueError as e:
        error = str(e)

    try:
        items = json.loads(items_json) if items_json else []
        if not isinstance(items, list) or not items:
            raise ValueError("At least one line item is required.")
    except Exception:
        items = []
        error = error or "Invalid line items payload."

    parsed_items = []
    if not error:
        for idx, it in enumerate(items):
            try:
                product_id = int(it.get("product_id"))
                description = (it.get("description") or "").strip()
                qty = float(it.get("qty"))
                rate = float(it.get("rate"))
                print_dual_units = int(it.get("print_dual_units") or 0)
                packing_multiplier = float(it.get("packing_multiplier") or 1.0)
            except Exception:
                error = f"Invalid values in item row {idx + 1}."
                break

            if qty <= 0:
                error = f"Qty must be greater than 0 in item row {idx + 1}."
                break
            if rate < 0:
                error = f"Rate cannot be negative in item row {idx + 1}."
                break
            if packing_multiplier <= 0:
                error = f"Packing multiplier must be greater than 0 in item row {idx + 1}."
                break
            if not description:
                error = f"Description is required in item row {idx + 1}."
                break

            amount = round(qty * rate * packing_multiplier, 2)
            parsed_items.append(
                {
                    "product_id": product_id,
                    "description": description,
                    "qty": qty,
                    "rate": rate,
                    "amount": amount,
                    "print_dual_units": print_dual_units,
                    "packing_multiplier": packing_multiplier,
                }
            )

    if not error:
        subtotal = round(sum(li["amount"] for li in parsed_items), 2)
        grand_total = round(subtotal - discount_amount, 2)
        if grand_total < 0:
            grand_total = 0.00

        is_quote = "generate_quote" in request.form
        
        # Use provided invoice number or generate one
        if is_quote:
            status = 'quote'
            if not invoice_number:
                invoice_number = f"Q-{get_next_invoice_number().replace('AK-', '')}"
            elif invoice_number.startswith("AK-"):
                invoice_number = "Q-" + invoice_number[3:]
            elif not invoice_number.startswith("Q-"):
                invoice_number = "Q-" + invoice_number
            amount_paid = 0
            remaining_amount = grand_total
        else:
            if not invoice_number:
                invoice_number = get_next_invoice_number()

            # Calculate amount_paid and remaining_amount based on payment_type
            if payment_type == 'cash':
                amount_paid = grand_total
                remaining_amount = 0
                status = 'paid'
            elif payment_type == 'cheque':
                amount_paid = grand_total
                remaining_amount = 0
                status = 'paid'
            elif payment_type == 'credit':
                # amount_paid comes from form (paid upfront field)
                # Validate it doesn't exceed grand_total
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
            else:
                status = 'unpaid'

        print(f"DEBUG sales_new: grand_total={grand_total}, amount_paid={amount_paid}, payment_type={payment_type}, remaining={remaining_amount}, status={status}")

        conn = get_connection()
        try:
            conn.execute("BEGIN")

            qty_total_by_product = defaultdict(float)
            for li in parsed_items:
                qty_total_by_product[li["product_id"]] += li["qty"] * li["packing_multiplier"]

            # Ensure stock is sufficient (aggregate per product for repeated items)
            if not is_quote:
                for product_id, qty_total in qty_total_by_product.items():
                    cur = conn.execute(
                        "SELECT stock_quantity, name FROM products WHERE id = ?",
                        (product_id,),
                    )
                    row = cur.fetchone()
                    if row is None:
                        raise ValueError("One or more selected products are invalid.")
                    stock_quantity = float(row["stock_quantity"] or 0)
                    product_name = row["name"] or "Unknown Product"
                    if stock_quantity + 1e-9 < qty_total:
                        raise ValueError(f"Insufficient stock for {product_name} (requested {qty_total}, available {stock_quantity}).")

            try:
                salesman_id = int(salesman_id_raw) if salesman_id_raw else current_user.id
            except ValueError:
                salesman_id = current_user.id
                
            cur = conn.execute(
                """
                INSERT INTO sales
                    (invoice_number, customer_id, invoice_date, due_date, terms, payment_type,
                     discount_amount, subtotal, grand_total, notes, status, amount_paid, remaining_amount, salesman_id)
                VALUES
                    (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    invoice_number,
                    customer_id,
                    invoice_date,
                    due_date or None,
                    terms or None,
                    payment_type,
                    discount_amount,
                    subtotal,
                    grand_total,
                    notes or None,
                    status,
                    amount_paid,
                    remaining_amount,
                    salesman_id,
                ),
            )
            sale_id = int(cur.lastrowid)

            for li in parsed_items:
                conn.execute(
                    """
                    INSERT INTO sale_items
                        (sale_id, product_id, description, qty, rate, amount, cost_price, print_dual_units, packing_multiplier)
                    VALUES
                        (?, ?, ?, ?, ?, ?, COALESCE((SELECT cost_price FROM products WHERE id = ?), 0), ?, ?)
                    """,
                    (
                        sale_id,
                        li["product_id"],
                        li["description"],
                        li["qty"],
                        li["rate"],
                        li["amount"],
                        li["product_id"],
                        li["print_dual_units"],
                        li["packing_multiplier"],
                    ),
                )

            # Deduct stock atomically (per product total)
            if not is_quote:
                for product_id, qty_total in qty_total_by_product.items():
                    cur = conn.execute("SELECT stock_quantity FROM products WHERE id = ?", (product_id,))
                    row = cur.fetchone()
                    old_stock = float(row["stock_quantity"] or 0) if row else 0

                    upd = conn.execute(
                        """
                        UPDATE products
                        SET stock_quantity = stock_quantity - ?
                        WHERE id = ? AND stock_quantity >= ?
                        """,
                        (qty_total, product_id, qty_total),
                    )
                    if upd.rowcount == 0:
                        cur = conn.execute(
                            "SELECT name FROM products WHERE id = ?",
                            (product_id,),
                        )
                        row = cur.fetchone()
                        product_name = row["name"] if row else "Unknown Product"
                        raise ValueError(f"Insufficient stock for {product_name}.")
                    else:
                        new_stock = old_stock - qty_total
                        conn.execute("""
                            INSERT INTO inventory_history (product_id, transaction_type, quantity_change, previous_stock, new_stock, reference)
                            VALUES (?, ?, ?, ?, ?, ?)
                        """, (product_id, 'OUT', -qty_total, old_stock, new_stock, f'Invoice #{invoice_number}'))

            conn.commit()
        except Exception as e:
            conn.rollback()
            error = str(e)
        finally:
            conn.close()

    if error:
        flash(error, "error")
        return redirect(url_for("sales"))

    if generate_invoice or is_quote:
        return redirect(url_for("sales_invoice_pdf", id=sale_id))

    flash("Sale saved successfully.", "success")
    return redirect(url_for("sales"))


@app.route("/sales/check-invoice", methods=["GET"])
@admin_required
def sales_check_invoice():
    invoice_number = request.args.get("n", "").strip()
    if not invoice_number:
        return jsonify({"exists": False})
    
    conn = get_connection()
    try:
        row = conn.execute(
            "SELECT id FROM sales WHERE invoice_number = ?",
            (invoice_number,),
        ).fetchone()
        return jsonify({"exists": row is not None})
    finally:
        conn.close()


@app.route("/sales/edit/<int:sale_id>", methods=["GET"])
@admin_required
def sales_edit(sale_id: int):
    conn = get_connection()
    try:
        # Get sale data
        sale = conn.execute(
            """
            SELECT
                s.id,
                s.invoice_number,
                s.customer_id,
                s.invoice_date,
                s.due_date,
                s.terms,
                s.payment_type,
                s.discount_amount,
                s.subtotal,
                s.grand_total,
                s.amount_paid,
                s.remaining_amount,
                s.notes,
                s.status,
                s.salesman_id,
                u.username AS salesman_name
            FROM sales s
            LEFT JOIN users u ON u.id = s.salesman_id
            WHERE s.id = ?
            """,
            (sale_id,),
        ).fetchone()
        
        if sale is None:
            flash("Sale not found.", "error")
            return redirect(url_for("sales"))
        
        # Get customer data
        customer = conn.execute(
            "SELECT id, name FROM customers WHERE id = ?",
            (sale["customer_id"],),
        ).fetchone()
        
        # Get sale items
        items = conn.execute(
            """
            SELECT
                si.product_id,
                si.description,
                si.qty,
                si.rate,
                si.amount,
                si.print_dual_units,
                COALESCE(si.packing_multiplier, 1.0) as packing_multiplier,
                p.stock_quantity
            FROM sale_items si
            LEFT JOIN products p ON p.id = si.product_id
            WHERE si.sale_id = ?
            """,
            (sale_id,),
        ).fetchall()
        
        # Convert to dict and add stock quantity
        edit_sale = dict(sale)
        edit_sale["customer_name"] = customer["name"] if customer else ""
        edit_sale["items"] = [dict(item, qty=float(item["qty"])) for item in items]
        print("DEBUG:", edit_sale.get("amount_paid"), edit_sale.get("remaining_amount"))
        
        # Get other data for the form
        customers = conn.execute(
            "SELECT id, name, terms FROM customers ORDER BY name COLLATE NOCASE"
        ).fetchall()
        
        recent_sales = conn.execute(
            """
            SELECT
                s.id,
                s.invoice_number,
                s.invoice_date,
                c.name AS customer_name,
                COUNT(si.id) AS item_count,
                COALESCE(s.subtotal, 0) AS subtotal,
                COALESCE(s.discount_amount, 0) AS discount_amount,
                COALESCE(s.grand_total, 0) AS grand_total,
                COALESCE(s.amount_paid, 0) AS amount_paid,
                COALESCE(s.remaining_amount, 0) AS remaining_amount,
                s.payment_type,
                s.status,
                u.username AS salesman_name
            FROM sales s
            LEFT JOIN users u ON u.id = s.salesman_id
            LEFT JOIN customers c ON c.id = s.customer_id
            LEFT JOIN sale_items si ON si.sale_id = s.id
            GROUP BY s.id
            ORDER BY s.invoice_date DESC, s.id DESC
            LIMIT 10
            """
        ).fetchall()
        
        # Get users for dropdown
        users_rows = conn.execute("SELECT id, username, role FROM users ORDER BY username").fetchall()
        users_list = [dict(r) for r in users_rows]
        
    finally:
        conn.close()
    
    return render_template(
        "sales.html",
        customers=[dict(c) for c in customers],
        recent_sales=[dict(r) for r in recent_sales],
        all_users=users_list,
        next_invoice_number=get_next_invoice_number(),
        today=date.today().isoformat(),
        edit_mode=True,
        edit_sale=edit_sale,
    )


@app.route("/sales/update/<int:sale_id>", methods=["POST"])
@admin_required
def sales_update(sale_id: int):
    customer_id_raw = (request.form.get("customer_id") or "").strip()
    invoice_date = (request.form.get("invoice_date") or "").strip()
    due_date = (request.form.get("due_date") or "").strip()
    terms = (request.form.get("terms") or "").strip()
    notes = request.form.get("notes") or ""
    invoice_number = (request.form.get("invoice_number") or "").strip()
    payment_type = (request.form.get("payment_type") or "").strip()
    discount_amount_raw = (request.form.get("discount_amount") or "").strip()
    items_json = request.form.get("items_json") or "[]"
    generate_invoice = "generate_invoice" in request.form
    amount_paid = float(request.form.get("amount_paid") or 0)
    remaining_amount = 0
    salesman_id_raw = (request.form.get("salesman_id") or "").strip()

    error = None

    try:
        is_quote = "generate_quote" in request.form
        if is_quote and not customer_id_raw:
            customer_id = None
        else:
            if not customer_id_raw:
                raise ValueError("Customer is required for saving a sale.")
            customer_id = int(customer_id_raw)
        if not invoice_date:
            raise ValueError("Invoice date is required.")
        discount_amount = float(discount_amount_raw) if discount_amount_raw else 0.0
        if discount_amount < 0:
            raise ValueError("Discount cannot be negative.")
        if payment_type not in ("cash", "cheque", "credit"):
            raise ValueError("Invalid payment type.")
        
        # Check if invoice number already exists (excluding current sale)
        if invoice_number:
            conn_check = get_connection()
            try:
                row = conn_check.execute(
                    "SELECT id FROM sales WHERE invoice_number = ? AND id != ?",
                    (invoice_number, sale_id),
                ).fetchone()
                if row is not None:
                    raise ValueError(f"Invoice number {invoice_number} already exists.")
            finally:
                conn_check.close()

        if customer_id is not None:
            conn_check = get_connection()
            try:
                row = conn_check.execute(
                    "SELECT id FROM customers WHERE id = ?",
                    (customer_id,),
                ).fetchone()
                if row is None:
                    raise ValueError("Customer not found.")
            finally:
                conn_check.close()
    except ValueError as e:
        error = str(e)

    try:
        items = json.loads(items_json) if items_json else []
        if not isinstance(items, list) or not items:
            raise ValueError("At least one line item is required.")
    except Exception:
        items = []
        error = error or "Invalid line items payload."

    parsed_items = []
    print("DEBUG items:", items)
    if not error:
        for idx, it in enumerate(items):
            try:
                product_id = int(it.get("product_id"))
                description = (it.get("description") or "").strip()
                qty = float(it.get("qty"))
                rate = float(it.get("rate"))
                print_dual_units = int(it.get("print_dual_units") or 0)
                packing_multiplier = float(it.get("packing_multiplier") or 1.0)
            except Exception:
                error = f"Invalid values in item row {idx + 1}."
                break

            if qty <= 0:
                error = f"Qty must be greater than 0 in item row {idx + 1}."
                break
            if rate < 0:
                error = f"Rate cannot be negative in item row {idx + 1}."
                break
            if packing_multiplier <= 0:
                error = f"Packing multiplier must be greater than 0 in item row {idx + 1}."
                break
            if not description:
                error = f"Description is required in item row {idx + 1}."
                break

            amount = round(qty * rate * packing_multiplier, 2)
            parsed_items.append(
                {
                    "product_id": product_id,
                    "description": description,
                    "qty": qty,
                    "rate": rate,
                    "amount": amount,
                    "print_dual_units": print_dual_units,
                    "packing_multiplier": packing_multiplier,
                }
            )

    if not error:
        subtotal = round(sum(li["amount"] for li in parsed_items), 2)
        grand_total = round(subtotal - discount_amount, 2)
        if grand_total < 0:
            grand_total = 0.00

        # Calculate amount_paid and remaining_amount based on payment_type
        if payment_type == 'cash':
            amount_paid = grand_total
            remaining_amount = 0
            status = 'paid'
        elif payment_type == 'cheque':
            amount_paid = grand_total
            remaining_amount = 0
            status = 'paid'
        elif payment_type == 'credit':
            # amount_paid comes from form (paid upfront field)
            # Validate it doesn't exceed grand_total
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
        else:
            status = 'unpaid'

        if "generate_quote" in request.form:
            from invoice_generator import generate_pdf_from_data
            conn_quote = get_connection()
            try:
                cust_row = conn_quote.execute("SELECT id, name, bill_address, ship_address, phone FROM customers WHERE id = ?", (customer_id,)).fetchone()
                customer_data = dict(cust_row) if cust_row else {"name": "Quotation", "bill_address": "", "ship_address": "", "phone": ""}
                
                for item in parsed_items:
                    prod = conn_quote.execute("SELECT name, brand FROM products WHERE id = ?", (item["product_id"],)).fetchone()
                    item["product_name"] = prod["name"] if prod else ""
                    item["product_brand"] = prod["brand"] if prod else ""
            finally:
                conn_quote.close()
                
            sale_data = {
                "invoice_number": f"Q-{invoice_number}" if invoice_number else f"Q-Sale-{sale_id}",
                "invoice_date": invoice_date,
                "due_date": due_date,
                "terms": terms,
                "subtotal": subtotal,
                "discount_amount": discount_amount,
                "grand_total": grand_total,
                "payment_type": payment_type,
                "amount_paid": amount_paid,
                "remaining_amount": remaining_amount
            }
            
            pdf_bytes = generate_pdf_from_data(sale_data, customer_data, parsed_items, is_quote=True)
            resp = Response(pdf_bytes, mimetype="application/pdf")
            resp.headers["Content-Disposition"] = f'attachment; filename="{sale_data["invoice_number"]}.pdf"'
            return resp

        conn = get_connection()
        try:
            conn.execute("BEGIN")

            # Get old sale items to restore stock
            old_items = conn.execute(
                """
                SELECT product_id, qty, COALESCE(packing_multiplier, 1.0) as packing_multiplier
                FROM sale_items
                WHERE sale_id = ?
                """,
                (sale_id,),
            ).fetchall()

            # Restore old stock
            old_qty_by_product = defaultdict(float)
            for item in old_items:
                old_qty_by_product[item["product_id"]] += float(item["qty"]) * float(item["packing_multiplier"])

            for product_id, qty_total in old_qty_by_product.items():
                cur = conn.execute("SELECT stock_quantity FROM products WHERE id = ?", (product_id,))
                row = cur.fetchone()
                old_stock = float(row["stock_quantity"] or 0) if row else 0
                new_stock = old_stock + qty_total
                
                conn.execute(
                    "UPDATE products SET stock_quantity = ? WHERE id = ?",
                    (new_stock, product_id),
                )
                
                conn.execute("""
                    INSERT INTO inventory_history (product_id, transaction_type, quantity_change, previous_stock, new_stock, reference)
                    VALUES (?, ?, ?, ?, ?, ?)
                """, (product_id, 'IN', qty_total, old_stock, new_stock, f'Invoice #{invoice_number} Edit Restore'))

            # Calculate new stock requirements
            new_qty_by_product = defaultdict(float)
            for li in parsed_items:
                new_qty_by_product[li["product_id"]] += li["qty"] * li["packing_multiplier"]

            # Check new stock availability
            for product_id, qty_total in new_qty_by_product.items():
                cur = conn.execute(
                    "SELECT stock_quantity, name FROM products WHERE id = ?",
                    (product_id,),
                )
                row = cur.fetchone()
                if row is None:
                    raise ValueError("One or more selected products are invalid.")
                stock_quantity = float(row["stock_quantity"] or 0)
                product_name = row["name"] or "Unknown Product"
                if stock_quantity + 1e-9 < qty_total:
                    raise ValueError(f"Insufficient stock for {product_name} (requested {qty_total}, available {stock_quantity}).")

            # Update sale record
            try:
                salesman_id = int(salesman_id_raw) if salesman_id_raw else current_user.id
            except ValueError:
                salesman_id = current_user.id
                
            conn.execute(
                """
                UPDATE sales
                SET invoice_number = ?, customer_id = ?, invoice_date = ?, due_date = ?,
                    terms = ?, payment_type = ?, discount_amount = ?, subtotal = ?,
                    grand_total = ?, notes = ?, status = ?, amount_paid = ?, remaining_amount = ?, salesman_id = ?
                WHERE id = ?
                """,
                (
                    invoice_number,
                    customer_id,
                    invoice_date,
                    due_date or None,
                    terms or None,
                    payment_type,
                    discount_amount,
                    subtotal,
                    grand_total,
                    notes or None,
                    status,
                    amount_paid,
                    remaining_amount,
                    salesman_id,
                    sale_id,
                ),
            )

            # Delete old sale items
            conn.execute("DELETE FROM sale_items WHERE sale_id = ?", (sale_id,))

            # Insert new sale items
            for li in parsed_items:
                conn.execute(
                    """
                    INSERT INTO sale_items
                        (sale_id, product_id, description, qty, rate, amount, cost_price, print_dual_units, packing_multiplier)
                    VALUES
                        (?, ?, ?, ?, ?, ?, COALESCE((SELECT cost_price FROM products WHERE id = ?), 0), ?, ?)
                    """,
                    (
                        sale_id,
                        li["product_id"],
                        li["description"],
                        li["qty"],
                        li["rate"],
                        li["amount"],
                        li["product_id"],
                        li["print_dual_units"],
                        li["packing_multiplier"],
                    ),
                )

            # Deduct new stock
            for product_id, qty_total in new_qty_by_product.items():
                cur = conn.execute("SELECT stock_quantity FROM products WHERE id = ?", (product_id,))
                row = cur.fetchone()
                old_stock = float(row["stock_quantity"] or 0) if row else 0

                upd = conn.execute(
                    """
                    UPDATE products
                    SET stock_quantity = stock_quantity - ?
                    WHERE id = ? AND stock_quantity >= ?
                    """,
                    (qty_total, product_id, qty_total),
                )
                if upd.rowcount == 0:
                    cur = conn.execute(
                        "SELECT name FROM products WHERE id = ?",
                        (product_id,),
                    )
                    row = cur.fetchone()
                    product_name = row["name"] if row else "Unknown Product"
                    raise ValueError(f"Insufficient stock for {product_name}.")
                else:
                    new_stock = old_stock - qty_total
                    conn.execute("""
                        INSERT INTO inventory_history (product_id, transaction_type, quantity_change, previous_stock, new_stock, reference)
                        VALUES (?, ?, ?, ?, ?, ?)
                    """, (product_id, 'OUT', -qty_total, old_stock, new_stock, f'Invoice #{invoice_number} Edit'))

            conn.commit()
        except Exception as e:
            conn.rollback()
            error = str(e)
        finally:
            conn.close()

    if error:
        flash(error, "error")
        return redirect(url_for("sales_edit", sale_id=sale_id))

    if generate_invoice:
        return redirect(url_for("sales_invoice_pdf", id=sale_id))

    flash("Sale updated successfully.", "success")
    return redirect(url_for("sales"))


@app.route("/sales/<int:sale_id>/details", methods=["GET"])
@login_required
def sale_details(sale_id: int):
    conn = get_connection()
    try:
        # Get sale details
        sale = conn.execute(
            """
            SELECT 
                s.id,
                s.invoice_number,
                s.invoice_date,
                s.due_date,
                s.terms,
                s.payment_type,
                s.status,
                s.subtotal,
                s.discount_amount,
                s.grand_total,
                s.amount_paid,
                s.remaining_amount,
                c.name as customer_name,
                u.username as salesman_name,
                (SELECT COALESCE(SUM(si.qty * COALESCE(si.packing_multiplier, 1.0) * si.cost_price), 0) FROM sale_items si WHERE si.sale_id = s.id) as total_cost
            FROM sales s
            LEFT JOIN customers c ON c.id = s.customer_id
            LEFT JOIN users u ON u.id = s.salesman_id
            WHERE s.id = ?
            """,
            (sale_id,),
        ).fetchone()
        
        if not sale:
            return jsonify({"error": "Sale not found"}), 404
        
        # Get sale items
        items = conn.execute(
            """
            SELECT 
                description,
                qty,
                rate,
                amount
            FROM sale_items
            WHERE sale_id = ?
            ORDER BY id
            """,
            (sale_id,),
        ).fetchall()
        
        rev = float(sale["grand_total"] or 0)
        cost = float(sale["total_cost"] or 0)
        profit_margin = round(((rev - cost) / rev * 100), 2) if rev > 0 else 0
        profit_amount = round(rev - cost, 2)

        return jsonify({
            "id": sale["id"],
            "invoice_number": sale["invoice_number"],
            "invoice_date": sale["invoice_date"],
            "due_date": sale["due_date"],
            "terms": sale["terms"],
            "payment_type": sale["payment_type"],
            "status": sale["status"],
            "subtotal": sale["subtotal"],
            "discount_amount": sale["discount_amount"],
            "grand_total": sale["grand_total"],
            "amount_paid": sale["amount_paid"],
            "remaining_amount": sale["remaining_amount"],
            "customer_name": sale["customer_name"],
            "salesman_name": sale["salesman_name"],
            "profit_margin": profit_margin,
            "profit_amount": profit_amount,
            "items": [dict(item) for item in items]
        })
    finally:
        conn.close()


@app.route("/sales/by-invoice/<invoice_number>", methods=["GET"])
@admin_required
def sale_by_invoice(invoice_number: str):
    conn = get_connection()
    try:
        # Get sale details by invoice number
        sale = conn.execute(
            """
            SELECT 
                s.invoice_number,
                s.invoice_date,
                s.due_date,
                s.terms,
                s.payment_type,
                s.status,
                s.subtotal,
                s.discount_amount,
                s.grand_total,
                s.amount_paid,
                s.remaining_amount,
                c.name as customer_name
            FROM sales s
            LEFT JOIN customers c ON c.id = s.customer_id
            WHERE s.invoice_number = ?
            """,
            (invoice_number,),
        ).fetchone()
        
        if not sale:
            return jsonify({"error": "Sale not found"}), 404
        
        # Get sale items
        items = conn.execute(
            """
            SELECT
                si.description,
                si.qty,
                si.rate,
                si.amount,
                p.name as product_name,
                p.unit
            FROM sale_items si
            LEFT JOIN products p ON p.id = si.product_id
            WHERE si.sale_id = (
                SELECT id FROM sales 
                WHERE invoice_number = ?
            )
            ORDER BY si.id
            """,
            (invoice_number,),
        ).fetchall()
        
        return jsonify({
            "invoice_number": sale["invoice_number"],
            "invoice_date": sale["invoice_date"],
            "customer_name": sale["customer_name"],
            "items": [dict(item) for item in items],
            "subtotal": float(sale["subtotal"]),
            "discount_amount": float(sale["discount_amount"]),
            "grand_total": float(sale["grand_total"]),
            "amount_paid": float(sale["amount_paid"]),
            "remaining_amount": float(sale["remaining_amount"])
        })
    finally:
        conn.close()


@app.route("/sales/<int:id>/invoice/pdf", methods=["GET"])
@admin_required
def sales_invoice_pdf(id: int):
    conn = get_connection()
    try:
        sale = conn.execute(
            """
            SELECT
                s.id,
                s.invoice_number,
                s.customer_id
            FROM sales s
            WHERE s.id = ?
            """,
            (id,),
        ).fetchone()
        if sale is None:
            return Response("Sale not found", status=404)

        customer = conn.execute(
            """
            SELECT id, name, bill_address, ship_address
            FROM customers
            WHERE id = ?
            """,
            (sale["customer_id"],),
        ).fetchone()
        if customer is None:
            customer = {"id": None, "name": "Quotation", "bill_address": "", "ship_address": ""}

        # Query sale items as requested (generator will also fetch).
        conn.execute(
            """
            SELECT
                si.id,
                si.product_id,
                si.description,
                si.qty,
                si.rate,
                si.amount
            FROM sale_items si
            WHERE si.sale_id = ?
            """,
            (id,),
        ).fetchall()
    finally:
        conn.close()

    pdf_bytes = generate_invoice_pdf(id)
    invoice_number = sale["invoice_number"] if sale else None
    filename = f"{invoice_number}.pdf" if invoice_number else f"AK-invoice-{id}.pdf"

    resp = Response(pdf_bytes, mimetype="application/pdf")
    resp.headers["Content-Disposition"] = f'inline; filename="{filename}"'
    return resp


@app.route("/sales/<int:sale_id>/mark_sale", methods=["POST"])
def sales_mark_sale(sale_id: int):
    conn = get_connection()
    try:
        conn.execute("BEGIN")
        sale = conn.execute("SELECT * FROM sales WHERE id = ?", (sale_id,)).fetchone()
        if not sale:
            return jsonify({"success": False, "message": "Sale not found"})
        
        if sale["status"] != "quote":
            return jsonify({"success": False, "message": "Only quotes can be marked as sales."})

        # Generate actual invoice number
        quote_invoice_num = sale["invoice_number"]
        if quote_invoice_num and quote_invoice_num.startswith("Q-"):
            potential_invoice_num = "AK-" + quote_invoice_num[2:]
            exists = conn.execute("SELECT 1 FROM sales WHERE invoice_number = ?", (potential_invoice_num,)).fetchone()
            if not exists:
                invoice_number = potential_invoice_num
            else:
                invoice_number = get_next_invoice_number()
        else:
            invoice_number = get_next_invoice_number()

        items = conn.execute("SELECT product_id, qty FROM sale_items WHERE sale_id = ?", (sale_id,)).fetchall()

        # Check stock first
        qty_total_by_product = defaultdict(float)
        for it in items:
            qty_total_by_product[it["product_id"]] += it["qty"]
            
        for product_id, qty_total in qty_total_by_product.items():
            row = conn.execute("SELECT stock_quantity, name FROM products WHERE id = ?", (product_id,)).fetchone()
            if row is None:
                raise ValueError("Invalid product found in quote.")
            stock_quantity = float(row["stock_quantity"] or 0)
            if stock_quantity + 1e-9 < qty_total:
                raise ValueError(f"Insufficient stock for {row['name']}.")

        # Update stock and write history
        for product_id, qty_total in qty_total_by_product.items():
            row = conn.execute("SELECT stock_quantity FROM products WHERE id = ?", (product_id,)).fetchone()
            old_stock = float(row["stock_quantity"] or 0) if row else 0
            
            upd = conn.execute(
                """
                UPDATE products
                SET stock_quantity = stock_quantity - ?
                WHERE id = ? AND stock_quantity >= ?
                """,
                (qty_total, product_id, qty_total)
            )
            if upd.rowcount == 0:
                raise ValueError("Stock became insufficient during update.")
            
            new_stock = old_stock - qty_total
            conn.execute("""
                INSERT INTO inventory_history (product_id, transaction_type, quantity_change, previous_stock, new_stock, reference)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (product_id, 'OUT', -qty_total, old_stock, new_stock, f'Invoice #{invoice_number}'))
            
        # Update sale record to unpaid and new invoice number
        conn.execute(
            """
            UPDATE sales
            SET status = 'unpaid', invoice_number = ?
            WHERE id = ?
            """,
            (invoice_number, sale_id)
        )

        conn.commit()
        return jsonify({"success": True, "new_invoice_number": invoice_number, "remaining_amount": sale["remaining_amount"]})
    except Exception as e:
        conn.rollback()
        return jsonify({"success": False, "message": str(e)})
    finally:
        conn.close()


@app.route("/sales/delete/<int:id>", methods=["POST"])
@admin_required
def sales_delete(id: int):
    conn = get_connection()
    try:
        conn.execute("BEGIN")

        items = conn.execute(
            """
            SELECT product_id, qty, COALESCE(packing_multiplier, 1.0) as packing_multiplier
            FROM sale_items
            WHERE sale_id = ?
            """,
            (id,),
        ).fetchall()

        cur = conn.execute("SELECT invoice_number FROM sales WHERE id = ?", (id,))
        row = cur.fetchone()
        invoice_number = row["invoice_number"] if row else str(id)
        
        conn.execute("DELETE FROM sale_items WHERE sale_id = ?", (id,))
        conn.execute("DELETE FROM sales WHERE id = ?", (id,))

        for it in items:
            cur = conn.execute("SELECT stock_quantity FROM products WHERE id = ?", (it["product_id"],))
            row = cur.fetchone()
            old_stock = float(row["stock_quantity"] or 0) if row else 0
            restored_qty = float(it["qty"]) * float(it["packing_multiplier"])
            new_stock = old_stock + restored_qty
            
            conn.execute(
                """
                UPDATE products
                SET stock_quantity = ?
                WHERE id = ?
                """,
                (new_stock, it["product_id"]),
            )
            
            conn.execute("""
                INSERT INTO inventory_history (product_id, transaction_type, quantity_change, previous_stock, new_stock, reference)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (it["product_id"], 'IN', restored_qty, old_stock, new_stock, f'Invoice #{invoice_number} Deleted'))

        conn.commit()
    except Exception:
        conn.rollback()
        flash("Failed to delete sale.", "error")
        return redirect(url_for("sales"))
    finally:
        conn.close()

    flash("Sale deleted successfully.", "success")
    return redirect(url_for("sales"))


@app.route('/sales/<int:sale_id>/record_payment', methods=['POST'])
@admin_required
def record_payment(sale_id):
    try:
        data = request.get_json()
        amount = float(data.get('amount', 0))
        payment_method = data.get('payment_method', 'Cash')
        notes = data.get('notes', '')

        conn = get_connection()
        sale = conn.execute('SELECT * FROM sales WHERE id = ?', (sale_id,)).fetchone()

        if not sale:
            return jsonify({'success': False, 'error': 'Sale not found'})

        if amount <= 0 or amount > float(sale['remaining_amount']):
            return jsonify({'success': False, 'error': 'Invalid amount'})

        new_amount_paid = float(sale['amount_paid']) + amount
        new_remaining = float(sale['remaining_amount']) - amount
        new_status = 'paid' if new_remaining <= 0.01 else 'partial'

        conn.execute('''UPDATE sales 
                      SET amount_paid = ?, remaining_amount = ?, status = ?, payment_type = ?
                      WHERE id = ?''',
                   (new_amount_paid, new_remaining, new_status, payment_method.lower(), sale_id))

        conn.commit()
        return jsonify({'success': True})

    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})


@app.route("/reports")
@admin_required
def reports():
    conn = get_connection()
    try:
        cur_c = conn.execute("SELECT id, name FROM customers ORDER BY name COLLATE NOCASE")
        customers = [dict(r) for r in cur_c.fetchall()]

        cur_p = conn.execute("SELECT id, name FROM products ORDER BY name COLLATE NOCASE")
        products = [dict(r) for r in cur_p.fetchall()]

        cur_b = conn.execute("SELECT DISTINCT brand FROM products WHERE brand IS NOT NULL AND brand != '' ORDER BY brand COLLATE NOCASE")
        brands = [r["brand"] for r in cur_b.fetchall()]

        cur_s = conn.execute("SELECT id, name FROM suppliers ORDER BY name COLLATE NOCASE")
        suppliers = [dict(r) for r in cur_s.fetchall()]
    finally:
        conn.close()

    return render_template(
        "reports.html",
        customers=customers,
        products=products,
        brands=brands,
        suppliers=suppliers
    )



def parse_date_filters(conditions, params):
    date_from = (request.args.get("date_from") or "").strip()
    date_to = (request.args.get("date_to") or "").strip()
    if date_from:
        conditions.append("s.invoice_date >= ?")
        params.append(date_from)
    if date_to:
        conditions.append("s.invoice_date <= ?")
        params.append(date_to)


@app.route("/reports/by-customer", methods=["GET"])
@admin_required
def reports_by_customer():
    conditions = ["s.customer_id IS NOT NULL"]
    params = []
    parse_date_filters(conditions, params)

    product_id = (request.args.get("product_id") or "").strip()
    brand = (request.args.get("brand") or "").strip()
    
    join_sale_items = False
    
    if product_id:
        conditions.append("si.product_id = ?")
        params.append(product_id)
        join_sale_items = True
    if brand:
        conditions.append("p.brand = ?")
        params.append(brand)
        join_sale_items = True
        
    where_sql = " AND ".join(conditions)

    conn = get_connection()
    try:
        # If we need to filter by product/brand, we must join sale_items for the summary.
        # But wait, to calculate profit margin we ALWAYS need sale_items.
        
        summary = conn.execute(
            f'''
            SELECT 
              c.id as customer_id,
              c.name as customer_name,
              c.area,
              COUNT(DISTINCT s.id) as invoice_count,
              COALESCE(SUM(si.amount), 0) as total_revenue,
              COALESCE(SUM(si.qty * COALESCE(si.packing_multiplier, 1.0) * si.cost_price), 0) as total_cost,
              (SELECT COALESCE(SUM(remaining_amount), 0) FROM sales WHERE customer_id = c.id) as outstanding,
              MAX(s.invoice_date) as last_sale_date
            FROM customers c
            JOIN sales s ON s.customer_id = c.id
            JOIN sale_items si ON si.sale_id = s.id
            JOIN products p ON p.id = si.product_id
            WHERE {where_sql}
            GROUP BY c.id, c.name, c.area
            ORDER BY total_revenue DESC
            '''
            ,
            params,
        ).fetchall()

        # For invoices, we just need to get the invoices that match the filters.
        invoices = conn.execute(
            f'''
            SELECT DISTINCT
                s.id as sale_id,
                s.customer_id,
                s.invoice_number,
                s.invoice_date,
                COALESCE(s.grand_total, 0) AS grand_total,
                s.payment_type,
                s.status,
                u.username AS salesman_name
            FROM sales s
            LEFT JOIN users u ON u.id = s.salesman_id
            JOIN sale_items si ON si.sale_id = s.id
            JOIN products p ON p.id = si.product_id
            WHERE {where_sql}
            ORDER BY s.invoice_date DESC, s.id DESC
            '''
            ,
            params,
        ).fetchall()
    finally:
        conn.close()

    by_customer = {}
    for row in summary:
        revenue = float(row["total_revenue"] or 0)
        cost = float(row["total_cost"] or 0)
        margin = ((revenue - cost) / revenue * 100) if revenue > 0 else 0
        by_customer[int(row["customer_id"])] = {
            "customer_id": int(row["customer_id"]),
            "customer_name": row["customer_name"] or "",
            "area": row["area"] or "",
            "invoice_count": int(row["invoice_count"] or 0),
            "total_revenue": revenue,
            "profit_margin": margin, "profit_amount": round(revenue - cost, 2) if "revenue" in locals() else (round(rev - cost, 2) if "rev" in locals() else 0),
            "outstanding": float(row["outstanding"] or 0),
            "last_sale_date": row["last_sale_date"] or "",
            "invoices": [],
        }

    for inv in invoices:
        cid = int(inv["customer_id"])
        if cid in by_customer:
            by_customer[cid]["invoices"].append(dict(inv))

    return jsonify(list(by_customer.values()))


@app.route("/reports/by-brand", methods=["GET"])
@admin_required
def reports_by_brand():
    conditions = ["s.customer_id IS NOT NULL", "p.brand IS NOT NULL", "p.brand != ''"]
    params = []
    parse_date_filters(conditions, params)

    customer_id = (request.args.get("customer_id") or "").strip()
    if customer_id:
        conditions.append("s.customer_id = ?")
        params.append(customer_id)
        
    where_sql = " AND ".join(conditions)

    conn = get_connection()
    try:
        rows = conn.execute(
            f'''
            SELECT
                p.brand,
                COALESCE(SUM(si.qty), 0) AS units_sold,
                COALESCE(SUM(si.amount), 0) AS total_revenue,
                COALESCE(SUM(si.qty * COALESCE(si.packing_multiplier, 1.0) * si.cost_price), 0) as total_cost
            FROM sale_items si
            JOIN products p ON p.id = si.product_id
            JOIN sales s ON s.id = si.sale_id
            WHERE {where_sql}
            GROUP BY p.brand
            ORDER BY total_revenue DESC
            ''',
            params,
        ).fetchall()
    finally:
        conn.close()

    result = []
    for r in rows:
        revenue = float(r["total_revenue"] or 0)
        cost = float(r["total_cost"] or 0)
        margin = ((revenue - cost) / revenue * 100) if revenue > 0 else 0
        result.append({
            "brand": r["brand"],
            "units_sold": float(r["units_sold"] or 0),
            "total_revenue": revenue,
            "profit_margin": margin, "profit_amount": round(revenue - cost, 2) if "revenue" in locals() else (round(rev - cost, 2) if "rev" in locals() else 0)
        })
    return jsonify(result)


@app.route("/reports/by-category", methods=["GET"])
@admin_required
def reports_by_category():
    conditions = ["s.customer_id IS NOT NULL"]
    params = []
    parse_date_filters(conditions, params)

    customer_id = (request.args.get("customer_id") or "").strip()
    if customer_id:
        conditions.append("s.customer_id = ?")
        params.append(customer_id)
        
    where_sql = " AND ".join(conditions)

    conn = get_connection()
    try:
        rows = conn.execute(
            f'''
            SELECT
                COALESCE(cat.name, 'Uncategorized') AS category_name,
                COALESCE(SUM(si.qty), 0) AS qty_sold,
                COALESCE(SUM(si.amount), 0) AS total_revenue,
                COALESCE(SUM(si.qty * COALESCE(si.packing_multiplier, 1.0) * si.cost_price), 0) as total_cost,
                SUM(p.stock_quantity) as current_stock
            FROM sale_items si
            JOIN products p ON p.id = si.product_id
            LEFT JOIN categories cat ON cat.id = p.category_id
            JOIN sales s ON s.id = si.sale_id
            WHERE {where_sql}
            GROUP BY p.category_id, cat.name
            ORDER BY total_revenue DESC
            ''',
            params,
        ).fetchall()
    finally:
        conn.close()

    result = []
    for r in rows:
        revenue = float(r["total_revenue"] or 0)
        cost = float(r["total_cost"] or 0)
        margin = ((revenue - cost) / revenue * 100) if revenue > 0 else 0
        
        result.append({
            "category_name": r["category_name"],
            "qty_sold": float(r["qty_sold"] or 0),
            "total_revenue": revenue,
            "profit_margin": margin, "profit_amount": round(revenue - cost, 2) if "revenue" in locals() else (round(rev - cost, 2) if "rev" in locals() else 0),
            "current_stock": float(r["current_stock"] or 0)
        })
    return jsonify(result)

@app.route("/reports/by-salesman", methods=["GET"])
@admin_required
def reports_by_salesman():
    conditions = ["s.customer_id IS NOT NULL"]
    params = []
    parse_date_filters(conditions, params)

    where_sql = " AND ".join(conditions)

    conn = get_connection()
    try:
        rows = conn.execute(
            f'''
            SELECT 
              MAX(s.salesman_id) as salesman_id,
              LOWER(COALESCE(u.username, 'admin')) as salesman_name,
              COUNT(DISTINCT s.id) as invoice_count,
              COALESCE(SUM(si.amount), 0) as total_revenue,
              COALESCE(SUM(si.qty * COALESCE(si.packing_multiplier, 1.0) * si.cost_price), 0) as total_cost,
              (SELECT COALESCE(SUM(remaining_amount), 0) FROM sales s2 
               LEFT JOIN users u2 ON u2.id = s2.salesman_id 
               WHERE LOWER(COALESCE(u2.username, 'admin')) = LOWER(COALESCE(u.username, 'admin'))) as outstanding
            FROM sales s
            LEFT JOIN users u ON u.id = s.salesman_id
            JOIN sale_items si ON si.sale_id = s.id
            JOIN products p ON p.id = si.product_id
            WHERE {where_sql}
            GROUP BY LOWER(COALESCE(u.username, 'admin'))
            ORDER BY total_revenue DESC
            '''
            ,
            params,
        ).fetchall()
    finally:
        conn.close()

    result = []
    for r in rows:
        revenue = float(r["total_revenue"] or 0)
        cost = float(r["total_cost"] or 0)
        margin = ((revenue - cost) / revenue * 100) if revenue > 0 else 0
        
        result.append({
            "salesman_id": r["salesman_id"] or 0,
            "salesman_name": r["salesman_name"],
            "invoice_count": int(r["invoice_count"] or 0),
            "total_revenue": revenue,
            "profit_margin": margin, 
            "profit_amount": round(revenue - cost, 2),
            "outstanding": float(r["outstanding"] or 0)
        })
    return jsonify(result)

@app.route("/reports/by-product", methods=["GET"])
@admin_required
def reports_by_product():
    conditions = ["s.customer_id IS NOT NULL"]
    params = []
    parse_date_filters(conditions, params)

    customer_id = (request.args.get("customer_id") or "").strip()
    if customer_id:
        conditions.append("s.customer_id = ?")
        params.append(customer_id)
        
    where_sql = " AND ".join(conditions)

    conn = get_connection()
    try:
        rows = conn.execute(
            f'''
            SELECT
                p.id as product_id,
                p.name as product_name,
                p.brand,
                COALESCE(cat.name, 'Uncategorized') as category,
                COALESCE(SUM(si.qty), 0) as units_sold,
                COALESCE(SUM(si.amount), 0) as total_revenue,
                COALESCE(SUM(si.qty * COALESCE(si.packing_multiplier, 1.0) * si.cost_price), 0) as total_cost,
                p.stock_quantity as current_stock
            FROM sale_items si
            JOIN products p ON p.id = si.product_id
            LEFT JOIN categories cat ON cat.id = p.category_id
            JOIN sales s ON s.id = si.sale_id
            WHERE {where_sql}
            GROUP BY p.id
            ORDER BY total_revenue DESC
            ''',
            params,
        ).fetchall()
    finally:
        conn.close()

    result = []
    for r in rows:
        revenue = float(r["total_revenue"] or 0)
        cost = float(r["total_cost"] or 0)
        margin = ((revenue - cost) / revenue * 100) if revenue > 0 else 0
        
        result.append({
            "product_name": r["product_name"] or "",
            "brand": r["brand"] or "",
            "category": r["category"] or "",
            "units_sold": float(r["units_sold"] or 0),
            "total_revenue": revenue,
            "profit_margin": margin, "profit_amount": round(revenue - cost, 2) if "revenue" in locals() else (round(rev - cost, 2) if "rev" in locals() else 0),
            "current_stock": float(r["current_stock"] or 0)
        })
    return jsonify(result)


@app.route("/reports/inventory-additions", methods=["GET"])
@admin_required
def reports_inventory_additions():
    conditions = [
        "ih.transaction_type = 'IN'",
        "ih.reference IN ('Initial Stock', 'Initial Stock (Legacy)', 'Manual Edit', 'Manual Edit (Edit Product)')",
    ]
    params = []
    
    date_from = request.args.get("date_from", "").strip()
    date_to = request.args.get("date_to", "").strip()
    if date_from:
        conditions.append("date(ih.created_at) >= ?")
        params.append(date_from)
    if date_to:
        conditions.append("date(ih.created_at) <= ?")
        params.append(date_to)

    supplier_id = request.args.get("supplier_id", "").strip()
    if supplier_id:
        conditions.append("p.supplier_id = ?")
        params.append(supplier_id)

    where_sql = " AND ".join(conditions)

    conn = get_connection()
    try:
        summary_rows = conn.execute(
            f'''
            SELECT
                supplier_name,
                SUM(total_added) as total_added,
                SUM(total_value) as total_value,
                SUM(current_stock) as total_remaining
            FROM (
                SELECT
                    p.id,
                    COALESCE(s.name, 'Untagged') AS supplier_name,
                    COALESCE(SUM(ih.quantity_change), 0) AS total_added,
                    COALESCE(SUM(ih.quantity_change * p.cost_price), 0) AS total_value,
                    p.stock_quantity AS current_stock
                FROM inventory_history ih
                JOIN products p ON p.id = ih.product_id
                LEFT JOIN suppliers s ON s.id = p.supplier_id
                WHERE {where_sql}
                GROUP BY p.id, COALESCE(s.name, 'Untagged'), p.stock_quantity
            )
            GROUP BY supplier_name
            ORDER BY total_added DESC
            ''',
            params,
        ).fetchall()

        date_rows = conn.execute(
            f'''
            SELECT
                date(ih.created_at) as addition_date,
                COALESCE(SUM(ih.quantity_change), 0) AS total_added,
                COALESCE(SUM(ih.quantity_change * p.cost_price), 0) AS total_value
            FROM inventory_history ih
            JOIN products p ON p.id = ih.product_id
            WHERE {where_sql}
            GROUP BY date(ih.created_at)
            ORDER BY addition_date DESC
            ''',
            params,
        ).fetchall()

        log_rows = conn.execute(
            f'''
            SELECT
                ih.created_at,
                p.name AS product_name,
                COALESCE(s.name, 'Untagged') AS supplier_name,
                ih.transaction_type,
                ih.reference,
                ih.quantity_change,
                (ih.quantity_change * p.cost_price) as value_added,
                p.stock_quantity AS quantity_remaining
            FROM inventory_history ih
            JOIN products p ON p.id = ih.product_id
            LEFT JOIN suppliers s ON s.id = p.supplier_id
            WHERE {where_sql}
            ORDER BY ih.created_at DESC
            ''',
            params,
        ).fetchall()
    finally:
        conn.close()

    summary_result = []
    for r in summary_rows:
        summary_result.append({
            "supplier_name": r["supplier_name"],
            "total_added": float(r["total_added"] or 0),
            "total_value": float(r["total_value"] or 0),
            "quantity_remaining": float(r["total_remaining"] or 0)
        })

    log_result = []
    for r in log_rows:
        log_result.append({
            "created_at": r["created_at"],
            "product_name": r["product_name"] or "",
            "supplier_name": r["supplier_name"],
            "transaction_type": r["transaction_type"],
            "reference": r["reference"],
            "quantity_change": float(r["quantity_change"] or 0),
            "value_added": float(r["value_added"] or 0),
            "quantity_remaining": float(r["quantity_remaining"] or 0)
        })

    date_result = []
    for r in date_rows:
        date_result.append({
            "addition_date": r["addition_date"],
            "total_added": float(r["total_added"] or 0),
            "total_value": float(r["total_value"] or 0)
        })

    return jsonify({"summary": summary_result, "date_summary": date_result, "log": log_result})

def _export_csv_bytes(rows, header):
    import csv
    import io
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(header)
    writer.writerows(rows)
    return output.getvalue().encode("utf-8")


@app.route("/reports/profit")
@admin_required
def reports_profit():
    from_date = request.args.get("from_date", "")
    to_date = request.args.get("to_date", "")
    brand = request.args.get("brand", "")
    customer = request.args.get("customer", "")
    product = request.args.get("product", "")
    
    conn = get_connection()
    try:
        query = '''
            SELECT 
                s.invoice_date,
                COUNT(DISTINCT s.id) as invoice_count,
                COALESCE(SUM(si.qty * si.rate), 0) as total_revenue,
                COALESCE(SUM(si.qty * COALESCE(si.packing_multiplier, 1.0) * si.cost_price), 0) as total_cost
            FROM sales s
            JOIN sale_items si ON si.sale_id = s.id
            JOIN products p ON si.product_id = p.id
            WHERE 1=1
        '''
        params = []
        if from_date:
            query += " AND s.invoice_date >= ?"
            params.append(from_date)
        if to_date:
            query += " AND s.invoice_date <= ?"
            params.append(to_date)
        if customer:
            query += " AND s.customer_id = ?"
            params.append(customer)
        if brand:
            query += " AND p.brand = ?"
            params.append(brand)
        if product:
            query += " AND p.id = ?"
            params.append(product)
            
        query += " GROUP BY s.invoice_date ORDER BY s.invoice_date ASC"
        
        rows = conn.execute(query, params).fetchall()
        
        result = []
        for r in rows:
            rev = float(r["total_revenue"] or 0)
            cost = float(r["total_cost"] or 0)
            margin = round(((rev - cost) / rev * 100), 2) if rev > 0 else 0
            profit_amt = round(rev - cost, 2)
            result.append({
                "date": r["invoice_date"],
                "invoice_count": r["invoice_count"],
                "total_revenue": rev,
                "total_cost": cost,
                "profit_margin": margin,
                "profit_amount": profit_amt
            })
            
        return jsonify(result)
    finally:
        conn.close()

@app.route("/reports/export/<type>", methods=["GET"])
@admin_required
def reports_export(type: str):
    import datetime
    year = datetime.datetime.now().year

    conn = get_connection()
    try:
        conditions = ["s.customer_id IS NOT NULL"]
        params = []
        parse_date_filters(conditions, params)

        if type == "customer":
            product_id = (request.args.get("product_id") or "").strip()
            brand = (request.args.get("brand") or "").strip()
            if product_id:
                conditions.append("si.product_id = ?")
                params.append(product_id)
            if brand:
                conditions.append("p.brand = ?")
                params.append(brand)
            where_sql = " AND ".join(conditions)

            rows = conn.execute(
                f'''
                SELECT 
                  c.name as customer_name,
                  c.area,
                  COUNT(DISTINCT s.id) as invoice_count,
                  COALESCE(SUM(si.amount), 0) as total_revenue,
                  COALESCE(SUM(si.qty * COALESCE(si.packing_multiplier, 1.0) * si.cost_price), 0) as total_cost,
                  (SELECT COALESCE(SUM(remaining_amount), 0) FROM sales WHERE customer_id = c.id) as outstanding,
                  MAX(s.invoice_date) as last_sale_date
                FROM customers c
                JOIN sales s ON s.customer_id = c.id
                JOIN sale_items si ON si.sale_id = s.id
                JOIN products p ON p.id = si.product_id
                WHERE {where_sql}
                GROUP BY c.id, c.name, c.area
                ORDER BY total_revenue DESC
                '''
                ,
                params,
            ).fetchall()
            header = ["Customer Name", "Area", "Total Invoices", "Total Revenue", "Profit Margin (%)", "Outstanding", "Last Sale Date"]
            csv_rows = []
            for r in rows:
                rev = float(r["total_revenue"] or 0)
                cost = float(r["total_cost"] or 0)
                margin = f'{((rev - cost) / rev * 100):.2f}' if rev > 0 else '0.00'
                csv_rows.append([
                    r["customer_name"] or "",
                    r["area"] or "",
                    str(r["invoice_count"] or 0),
                    f'{rev:.2f}',
                    margin,
                    f'{float(r["outstanding"] or 0):.2f}',
                    r["last_sale_date"] or ""
                ])
            filename = f"sales_by_customer_{year}.csv"

        elif type == "brand":
            customer_id = (request.args.get("customer_id") or "").strip()
            if customer_id:
                conditions.append("s.customer_id = ?")
                params.append(customer_id)
            conditions.extend(["p.brand IS NOT NULL", "p.brand != ''"])
            where_sql = " AND ".join(conditions)

            rows = conn.execute(
                f'''
                SELECT
                    p.brand,
                    COALESCE(SUM(si.qty), 0) AS units_sold,
                    COALESCE(SUM(si.amount), 0) AS total_revenue,
                    COALESCE(SUM(si.qty * COALESCE(si.packing_multiplier, 1.0) * si.cost_price), 0) as total_cost
                FROM sale_items si
                JOIN products p ON p.id = si.product_id
                JOIN sales s ON s.id = si.sale_id
                WHERE {where_sql}
                GROUP BY p.brand
                ORDER BY total_revenue DESC
                ''',
                params,
            ).fetchall()
            header = ["Brand Name", "Units Sold", "Total Revenue", "Profit Margin (%)"]
            csv_rows = []
            for r in rows:
                rev = float(r["total_revenue"] or 0)
                cost = float(r["total_cost"] or 0)
                margin = f'{((rev - cost) / rev * 100):.2f}' if rev > 0 else '0.00'
                csv_rows.append([
                    r["brand"] or "Unbranded",
                    f'{float(r["units_sold"] or 0):.3f}',
                    f'{rev:.2f}',
                    margin
                ])
            filename = f"sales_by_brand_{year}.csv"

        elif type == "category":
            customer_id = (request.args.get("customer_id") or "").strip()
            if customer_id:
                conditions.append("s.customer_id = ?")
                params.append(customer_id)
            where_sql = " AND ".join(conditions)

            rows = conn.execute(
                f'''
                SELECT
                    COALESCE(cat.name, 'Uncategorized') AS category_name,
                    COALESCE(SUM(si.qty), 0) AS qty_sold,
                    COALESCE(SUM(si.amount), 0) AS total_revenue,
                    COALESCE(SUM(si.qty * COALESCE(si.packing_multiplier, 1.0) * si.cost_price), 0) as total_cost,
                    SUM(p.stock_quantity) as current_stock
                FROM sale_items si
                JOIN products p ON p.id = si.product_id
                LEFT JOIN categories cat ON cat.id = p.category_id
                JOIN sales s ON s.id = si.sale_id
                WHERE {where_sql}
                GROUP BY p.category_id, cat.name
                ORDER BY total_revenue DESC
                ''',
                params,
            ).fetchall()
            header = ["Category", "Total Items Sold (Qty)", "Total Revenue", "Profit Margin (%)", "Current Stock"]
            csv_rows = []
            for r in rows:
                rev = float(r["total_revenue"] or 0)
                cost = float(r["total_cost"] or 0)
                margin = f'{((rev - cost) / rev * 100):.2f}' if rev > 0 else '0.00'
                csv_rows.append([
                    r["category_name"] or "",
                    f'{float(r["qty_sold"] or 0):.3f}',
                    f'{rev:.2f}',
                    margin,
                    f'{float(r["current_stock"] or 0):.3f}'
                ])
            filename = f"sales_by_category_{year}.csv"

        elif type == "product":
            customer_id = (request.args.get("customer_id") or "").strip()
            if customer_id:
                conditions.append("s.customer_id = ?")
                params.append(customer_id)
            where_sql = " AND ".join(conditions)

            rows = conn.execute(
                f'''
                SELECT
                    p.name as product_name,
                    p.brand,
                    COALESCE(cat.name, 'Uncategorized') as category,
                    COALESCE(SUM(si.qty), 0) as units_sold,
                    COALESCE(SUM(si.amount), 0) as total_revenue,
                    COALESCE(SUM(si.qty * COALESCE(si.packing_multiplier, 1.0) * si.cost_price), 0) as total_cost,
                    p.stock_quantity as current_stock
                FROM sale_items si
                JOIN products p ON p.id = si.product_id
                LEFT JOIN categories cat ON cat.id = p.category_id
                JOIN sales s ON s.id = si.sale_id
                WHERE {where_sql}
                GROUP BY p.id
                ORDER BY total_revenue DESC
                ''',
                params,
            ).fetchall()
            header = ["#", "Product Name", "Brand", "Category", "Units Sold", "Total Revenue", "Profit Margin (%)", "Current Stock"]
            csv_rows = []
            for i, r in enumerate(rows, start=1):
                rev = float(r["total_revenue"] or 0)
                cost = float(r["total_cost"] or 0)
                margin = f'{((rev - cost) / rev * 100):.2f}' if rev > 0 else '0.00'
                csv_rows.append([
                    str(i),
                    r["product_name"] or "",
                    r["brand"] or "",
                    r["category"] or "",
                    f'{float(r["units_sold"] or 0):.3f}',
                    f'{rev:.2f}',
                    margin,
                    f'{float(r["current_stock"] or 0):.3f}'
                ])
            filename = f"sales_by_product_{year}.csv"

        else:
            return Response("Invalid export type", status=400)
    finally:
        conn.close()

    csv_bytes = _export_csv_bytes(csv_rows, header)
    resp = Response(csv_bytes, mimetype="text/csv")
    resp.headers["Content-Disposition"] = f'attachment; filename="{filename}"'
    return resp

@app.route("/users")
@admin_required
def users_list():
    conn = get_connection()
    try:
        users = conn.execute("SELECT id, username, role, is_active FROM users").fetchall()
        return render_template("users.html", users=[dict(u) for u in users])
    finally:
        conn.close()

@app.route("/users/add", methods=["POST"])
@admin_required
def users_add():
    username = (request.form.get("username") or "").strip()
    password = (request.form.get("password") or "").strip()
    role = (request.form.get("role") or "salesman").strip()
    if not username or not password:
        return jsonify({"ok": False, "error": "Username and password are required."}), 400
    
    conn = get_connection()
    try:
        conn.execute(
            "INSERT INTO users (username, password_hash, role) VALUES (?, ?, ?)",
            (username, generate_password_hash(password, method="pbkdf2:sha256"), role)
        )
        conn.commit()
        return jsonify({"ok": True})
    except sqlite3.IntegrityError:
        return jsonify({"ok": False, "error": "Username already exists."}), 409
    finally:
        conn.close()
@app.route("/users/toggle_active/<int:user_id>", methods=["POST"])
@admin_required
def users_toggle_active(user_id):
    conn = get_connection()
    try:
        cur = conn.execute("SELECT is_active FROM users WHERE id = ?", (user_id,))
        row = cur.fetchone()
        if row:
            new_active = 0 if row["is_active"] == 1 else 1
            conn.execute("UPDATE users SET is_active = ? WHERE id = ?", (new_active, user_id))
            conn.commit()
    finally:
        conn.close()
    return redirect(url_for("users_list"))

@app.route("/users/reset_password", methods=["POST"])
@admin_required
def users_reset_password():
    user_id = request.form.get("user_id")
    new_password = request.form.get("new_password")
    if not user_id or not new_password:
        return jsonify({"ok": False, "error": "User ID and new password are required."}), 400
    
    conn = get_connection()
    try:
        conn.execute(
            "UPDATE users SET password_hash = ? WHERE id = ?",
            (generate_password_hash(new_password, method="pbkdf2:sha256"), user_id)
        )
        conn.commit()
        return jsonify({"ok": True})
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500
    finally:
        conn.close()

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
    customer_bill = (data.get("customer_bill") or "").strip()
    customer_ship = (data.get("customer_ship") or "").strip()
    customer_state = (data.get("customer_state") or "").strip()
    customer_email = (data.get("customer_email") or "").strip()
    customer_terms = (data.get("customer_terms") or "").strip()
    
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
                "INSERT INTO customers (name, bill_address, ship_address, area, state, phone, email, terms) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                (customer_name, customer_bill, customer_ship, customer_area, customer_state, customer_phone, customer_email, customer_terms)
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

        # Validate stock quantity
        qty_total_by_product = defaultdict(float)
        for li in parsed_items:
            qty_total_by_product[li["product_id"]] += li["qty"]
            
        for product_id, qty_total in qty_total_by_product.items():
            cur = conn.execute("SELECT name, stock_quantity FROM products WHERE id = ?", (product_id,))
            row = cur.fetchone()
            if not row:
                raise ValueError("One or more selected products are invalid.")
            stock_quantity = float(row["stock_quantity"] or 0)
            if stock_quantity + 1e-9 < qty_total:
                raise ValueError(f"Insufficient stock for {row['name']} (requested {qty_total}, available {stock_quantity}).")

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
        
        print(f"DEBUG pos_submit_order: grand_total={grand_total}, amount_paid={amount_paid}, payment_type={payment_type}, remaining={remaining_amount}, status={status}")

        # Insert sale
        cur = conn.execute(
            """
            INSERT INTO sales
                (invoice_number, customer_id, invoice_date, due_date, terms, payment_type,
                 subtotal, grand_total, status, amount_paid, remaining_amount, salesman_id)
            VALUES
                (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                invoice_number, customer_id, invoice_date, data.get("due_date"), data.get("customer_terms"), payment_type,
                subtotal, grand_total, status, amount_paid, remaining_amount, current_user.id
            )
        )
        sale_id = int(cur.lastrowid)

        # Insert items and deduct stock
        for li in parsed_items:
            conn.execute(
                """
                INSERT INTO sale_items (sale_id, product_id, description, qty, rate, amount, cost_price)
                VALUES (?, ?, ?, ?, ?, ?, COALESCE((SELECT cost_price FROM products WHERE id = ?), 0))
                """,
                (sale_id, li["product_id"], li["description"], li["qty"], li["rate"], li["amount"], li["product_id"])
            )
            
            conn.execute(
                """
                UPDATE products
                SET stock_quantity = COALESCE(stock_quantity, 0) - ?
                WHERE id = ?
                """,
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




@app.route("/purchases")
@login_required
def purchases():
    search = request.args.get('search', '').strip()
    supplier_id = request.args.get('supplier_id', '')
    start_date = request.args.get('start_date', '')
    end_date = request.args.get('end_date', '')
    
    conn = get_connection()
    try:
        query = '''
            SELECT p.id, p.reference_number, p.purchase_date, p.grand_total, p.amount_paid, p.remaining_amount, p.status, s.name as supplier_name
            FROM purchases p
            LEFT JOIN suppliers s ON p.supplier_id = s.id
            WHERE 1=1
        '''
        params = []
        
        if search:
            query += ' AND (p.reference_number LIKE ? OR p.id LIKE ?)'
            params.extend(['%'+search+'%', '%'+search+'%'])
        
        if supplier_id:
            query += ' AND p.supplier_id = ?'
            params.append(supplier_id)
            
        if start_date:
            query += ' AND p.purchase_date >= ?'
            params.append(start_date)
            
        if end_date:
            query += ' AND p.purchase_date <= ?'
            params.append(end_date)
            
        query += ' ORDER BY p.purchase_date DESC, p.id DESC'
        
        cur = conn.execute(query, params)
        rows = cur.fetchall()
        
        suppliers = conn.execute('SELECT id, name FROM suppliers ORDER BY name COLLATE NOCASE ASC').fetchall()
    finally:
        conn.close()
    return render_template("purchases.html", purchases=rows, suppliers=suppliers, filters={'search': search, 'supplier_id': supplier_id, 'start_date': start_date, 'end_date': end_date})

@app.route("/purchases/new", methods=["GET", "POST"])
@admin_required
def new_purchase():
    if request.method == "GET":
        conn = get_connection()
        try:
            suppliers = [dict(row) for row in conn.execute("SELECT id, name FROM suppliers ORDER BY name COLLATE NOCASE ASC").fetchall()]
            products = [dict(row) for row in conn.execute("SELECT id, name, cost_price, unit FROM products ORDER BY name COLLATE NOCASE ASC").fetchall()]
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
        other_charges = float(data.get("other_charges", 0))

        if not supplier_id or not items:
            return jsonify({"ok": False, "error": "Missing supplier or items"}), 400

        conn = get_connection()
        try:
            conn.execute("BEGIN")
            
            subtotal = sum(float(item.get("qty", 0)) * float(item.get("cost_price", 0)) for item in items)
            grand_total = subtotal + other_charges
            amount_paid = payment_amount
            remaining_amount = grand_total - amount_paid
            
            status = 'unpaid'
            if amount_paid >= grand_total:
                status = 'paid'
            elif amount_paid > 0:
                status = 'partial'

            cur = conn.execute('''
                INSERT INTO purchases (supplier_id, reference_number, purchase_date, subtotal, other_charges, grand_total, amount_paid, remaining_amount, status)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (supplier_id, reference_number, purchase_date, subtotal, other_charges, grand_total, amount_paid, remaining_amount, status))
            
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

if __name__ == "__main__":
    desired_port = int(os.environ.get("PORT", "5000"))
    ports_to_try = [desired_port, 5001, 5050]
    last_error = None
    for port in ports_to_try:
        try:
            app.run(host="0.0.0.0", port=port, debug=True)
            break
        except OSError as e:
            last_error = e
            continue
    else:
        if last_error:
            raise last_error
