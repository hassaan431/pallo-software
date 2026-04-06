import os
import json
import sqlite3

import csv

from datetime import date

from collections import defaultdict

from database import get_connection, get_next_invoice_number, get_user_by_id, get_user_by_username, init_db

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
from werkzeug.security import check_password_hash

from invoice_generator import generate_invoice_pdf

app = Flask(__name__)
app.secret_key = "change-this-secret-key-for-local-use"

login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = "login"
login_manager.login_message = None


class User(UserMixin):
    def __init__(self, db_id: int, username: str):
        self.id = db_id
        self.username = username


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
    return User(row["id"], row["username"])


@app.route("/")
def index():
    return redirect(url_for("login"))


@app.route("/login", methods=["GET", "POST"])
def login():
    if current_user.is_authenticated:
        return redirect(url_for("dashboard"))
    if request.method == "POST":
        username = (request.form.get("username") or "").strip()
        password = request.form.get("password") or ""
        row = get_user_by_username(username)
        if row is not None and check_password_hash(row["password_hash"], password):
            login_user(User(row["id"], row["username"]), remember=True)
            next_url = request.args.get("next")
            if next_url and next_url.startswith("/"):
                return redirect(next_url)
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


@app.route("/dashboard")
@login_required
def dashboard():
    conn = get_connection()
    try:
        # Get total products
        total_products = conn.execute("SELECT COUNT(*) as count FROM products").fetchone()["count"]
        
        # Get total customers
        total_customers = conn.execute("SELECT COUNT(*) as count FROM customers").fetchone()["count"]
        
        # Get today's sales
        today = date.today().isoformat()
        todays_sales = conn.execute(
            "SELECT COUNT(*) as count FROM sales WHERE invoice_date = ?", 
            (today,)
        ).fetchone()["count"]
        
        # Get monthly revenue
        now = date.today()
        current_month = now.month
        current_year = now.year
        monthly_revenue = conn.execute(
            """
            SELECT COALESCE(SUM(grand_total), 0) as total 
            FROM sales 
            WHERE strftime('%m', invoice_date) = ? AND strftime('%Y', invoice_date) = ?
            """,
            (f"{current_month:02d}", str(current_year))
        ).fetchone()["total"]
        
        # Get recent sales (last 5)
        recent_sales = conn.execute(
            """
            SELECT
                s.id,
                s.invoice_number,
                s.invoice_date,
                c.name AS customer_name,
                s.grand_total,
                s.payment_type,
                s.status
            FROM sales s
            LEFT JOIN customers c ON c.id = s.customer_id
            ORDER BY s.invoice_date DESC, s.id DESC
            LIMIT 5
            """
        ).fetchall()
        
    finally:
        conn.close()
    
    return render_template(
        "dashboard.html",
        total_products=total_products,
        total_customers=total_customers,
        todays_sales=todays_sales,
        monthly_revenue=float(monthly_revenue),
        recent_sales=[dict(sale) for sale in recent_sales]
    )


@app.route("/inventory")
@login_required
def inventory():
    conn = get_connection()
    try:
        cur = conn.execute(
            """
            SELECT
                p.id,
                p.name,
                p.brand,
                p.unit,
                p.cost_price,
                p.selling_price,
                p.stock_quantity,
                p.category_id,
                c.name AS category_name
            FROM products p
            LEFT JOIN categories c ON p.category_id = c.id
            ORDER BY p.name COLLATE NOCASE
            """
        )
        products = [dict(row) for row in cur.fetchall()]

        variants_by_product = {}
        product_ids = [int(p["id"]) for p in products]
        if product_ids:
            placeholders = ",".join(["?"] * len(product_ids))
            v_cur = conn.execute(
                f"""
                SELECT
                    product_id,
                    size,
                    flavor,
                    price_adjustment
                FROM product_variants
                WHERE product_id IN ({placeholders})
                ORDER BY id ASC
                """,
                tuple(product_ids),
            )
            for v in v_cur.fetchall():
                pid = int(v["product_id"])
                variants_by_product.setdefault(pid, []).append(
                    {
                        "size": v["size"] or "",
                        "flavor": v["flavor"] or "",
                        "price_adjustment": float(v["price_adjustment"] or 0),
                    }
                )

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
    finally:
        conn.close()

    return render_template(
        "inventory.html",
        products=products,
        categories=categories,
        variants_by_product=variants_by_product,
        total_products=total_products,
        total_stock_value=total_stock_value,
        low_stock_count=low_stock_count,
    )


@app.route("/inventory/add", methods=["POST"])
@login_required
def inventory_add():
    product_name = (request.form.get("product_name") or "").strip()
    brand = (request.form.get("brand") or "").strip()
    if brand == "__add_new__":
        brand = ""
    unit = (request.form.get("unit") or "Each").strip()
    category_id_raw = (request.form.get("category_id") or "").strip()
    variants_json = (request.form.get("variants_json") or "").strip()

    try:
        category_id = int(category_id_raw)
        cost_price = float(request.form.get("cost_price") or 0)
        selling_price = float(request.form.get("selling_price") or 0)
        stock_quantity = int(float(request.form.get("stock_quantity") or 0))
    except ValueError:
        return redirect(url_for("inventory"))

    if not product_name or not category_id:
        return redirect(url_for("inventory"))

    conn = get_connection()
    try:
        conn.execute("BEGIN")
        cur = conn.execute(
            """
            INSERT INTO products
                (name, category_id, brand, unit, cost_price, selling_price, stock_quantity)
            VALUES
                (?, ?, ?, ?, ?, ?, ?)
            """,
            (product_name, category_id, brand or None, unit, cost_price, selling_price, stock_quantity),
        )
        product_id = int(cur.lastrowid)

        # Keep brands table in sync for the Brand dropdown.
        if brand:
            conn.execute("INSERT OR IGNORE INTO brands (name) VALUES (?)", (brand,))

        # Save variants (optional)
        try:
            variants = json.loads(variants_json) if variants_json else []
        except Exception:
            variants = []

        conn.execute("DELETE FROM product_variants WHERE product_id = ?", (product_id,))
        for v in variants if isinstance(variants, list) else []:
            if not isinstance(v, dict):
                continue
            size = (v.get("size") or "").strip()
            flavor = (v.get("flavor") or "").strip()
            raw_adj = v.get("price_adjustment", 0)
            try:
                adj = float(raw_adj or 0)
            except (TypeError, ValueError):
                adj = 0.0
            if not size and not flavor:
                continue
            conn.execute(
                """
                INSERT INTO product_variants (product_id, size, flavor, price_adjustment)
                VALUES (?, ?, ?, ?)
                """,
                (product_id, size or None, flavor or None, adj),
            )
        conn.commit()
    finally:
        conn.close()

    return redirect(url_for("inventory"))


@app.route("/inventory/edit/<int:product_id>", methods=["POST"])
@login_required
def inventory_edit(product_id: int):
    product_name = (request.form.get("product_name") or "").strip()
    brand = (request.form.get("brand") or "").strip()
    if brand == "__add_new__":
        brand = ""
    unit = (request.form.get("unit") or "Each").strip()
    category_id_raw = (request.form.get("category_id") or "").strip()
    variants_json = (request.form.get("variants_json") or "").strip()

    try:
        category_id = int(category_id_raw)
        cost_price = float(request.form.get("cost_price") or 0)
        selling_price = float(request.form.get("selling_price") or 0)
        stock_quantity = int(float(request.form.get("stock_quantity") or 0))
    except ValueError:
        return redirect(url_for("inventory"))

    if not product_name or not category_id:
        return redirect(url_for("inventory"))

    conn = get_connection()
    try:
        conn.execute("BEGIN")
        conn.execute(
            """
            UPDATE products
            SET
                name = ?,
                brand = ?,
                category_id = ?,
                unit = ?,
                cost_price = ?,
                selling_price = ?,
                stock_quantity = ?
            WHERE id = ?
            """,
            (
                product_name,
                brand or None,
                category_id,
                unit,
                cost_price,
                selling_price,
                stock_quantity,
                product_id,
            ),
        )

        # Keep brands table in sync for the Brand dropdown.
        if brand:
            conn.execute("INSERT OR IGNORE INTO brands (name) VALUES (?)", (brand,))

        # Save variants (optional)
        try:
            variants = json.loads(variants_json) if variants_json else []
        except Exception:
            variants = []

        conn.execute("DELETE FROM product_variants WHERE product_id = ?", (product_id,))
        for v in variants if isinstance(variants, list) else []:
            if not isinstance(v, dict):
                continue
            size = (v.get("size") or "").strip()
            flavor = (v.get("flavor") or "").strip()
            raw_adj = v.get("price_adjustment", 0)
            try:
                adj = float(raw_adj or 0)
            except (TypeError, ValueError):
                adj = 0.0
            if not size and not flavor:
                continue
            conn.execute(
                """
                INSERT INTO product_variants (product_id, size, flavor, price_adjustment)
                VALUES (?, ?, ?, ?)
                """,
                (product_id, size or None, flavor or None, adj),
            )
        conn.commit()
    finally:
        conn.close()

    return redirect(url_for("inventory"))


@app.route("/inventory/delete/<int:product_id>", methods=["POST"])
@login_required
def inventory_delete(product_id: int):
    is_ajax = request.headers.get("X-Requested-With") == "fetch"

    conn = get_connection()
    ok = False
    error = None
    try:
        conn.execute("DELETE FROM product_variants WHERE product_id = ?", (product_id,))
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


@app.route("/categories/add", methods=["POST"])
@login_required
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
@login_required
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
@login_required
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
@login_required
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
                p.selling_price AS selling_price
            FROM products p
            LEFT JOIN brands b
                ON LOWER(b.name) = LOWER(p.brand)
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


@app.route("/customers")
@login_required
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
@login_required
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
@login_required
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
@login_required
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


@app.route("/customers/<int:customer_id>/history", methods=["GET"])
@login_required
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
@login_required
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
                COALESCE(s.remaining_amount, 0) AS remaining_amount
            FROM sales s
            LEFT JOIN customers c ON c.id = s.customer_id
            LEFT JOIN sale_items si ON si.sale_id = s.id
            GROUP BY s.id
            ORDER BY s.invoice_date DESC, s.id DESC
            LIMIT 10
            """
        ).fetchall()
        recent_sales = [dict(r) for r in recent_sales_rows]
    finally:
        conn.close()

    return render_template(
        "sales.html",
        customers=customers_list,
        recent_sales=recent_sales,
        next_invoice_number=get_next_invoice_number(),
        today=date.today().isoformat(),
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
                    unit,
                    stock_quantity
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
                    unit,
                    stock_quantity
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
                    "unit": r["unit"],
                    "stock_quantity": r["stock_quantity"],
                }
            )
        return jsonify(results)
    finally:
        conn.close()


@app.route("/products/<int:product_id>/variants", methods=["GET"])
@login_required
def product_variants(product_id: int):
    conn = get_connection()
    try:
        variants = conn.execute(
            """
            SELECT
                id,
                size,
                flavor,
                price_adjustment
            FROM product_variants
            WHERE product_id = ?
            ORDER BY size, flavor
            """,
            (product_id,),
        ).fetchall()
        
        return jsonify([dict(v) for v in variants])
    finally:
        conn.close()


@app.route("/sales/data", methods=["GET"])
@login_required
def sales_data():
    date_from = (request.args.get("date_from") or "").strip()
    date_to = (request.args.get("date_to") or "").strip()
    customer_id = (request.args.get("customer_id") or "").strip()
    payment_type = (request.args.get("payment_type") or "").strip()

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
                c.name as customer_name
            FROM sales s
            LEFT JOIN customers c ON c.id = s.customer_id
            {where_sql}
            ORDER BY s.id DESC
            """
        , params)
        return jsonify([dict(r) for r in cur.fetchall()])
    finally:
        conn.close()


@app.route("/sales/new", methods=["POST"])
@login_required
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
    discount_amount_raw = (request.form.get("discount_amount") or "").strip()
    items_json = request.form.get("items_json") or "[]"
    generate_invoice = "generate_invoice" in request.form

    error = None

    try:
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
            except Exception:
                error = f"Invalid values in item row {idx + 1}."
                break

            if qty < 0.01:
                error = f"Qty must be at least 0.01 in item row {idx + 1}."
                break
            if rate < 0:
                error = f"Rate cannot be negative in item row {idx + 1}."
                break
            if not description:
                error = f"Description is required in item row {idx + 1}."
                break

            amount = round(qty * rate, 2)
            parsed_items.append(
                {
                    "product_id": product_id,
                    "description": description,
                    "qty": qty,
                    "rate": rate,
                    "amount": amount,
                }
            )

    if not error:
        subtotal = round(sum(li["amount"] for li in parsed_items), 2)
        grand_total = round(subtotal - discount_amount, 2)
        if grand_total < 0:
            grand_total = 0.00

        # Use provided invoice number or generate one
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

        conn = get_connection()
        try:
            conn.execute("BEGIN")

            qty_total_by_product = defaultdict(float)
            for li in parsed_items:
                qty_total_by_product[li["product_id"]] += li["qty"]

            # Ensure stock is sufficient (aggregate per product for repeated items)
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

            cur = conn.execute(
                """
                INSERT INTO sales
                    (invoice_number, customer_id, invoice_date, due_date, terms, payment_type,
                     discount_amount, subtotal, grand_total, notes, status, amount_paid, remaining_amount)
                VALUES
                    (?, ?, ?, ?, ?, ?,
                     ?, ?, ?, ?, ?, ?, ?)
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
                ),
            )
            sale_id = int(cur.lastrowid)

            for li in parsed_items:
                conn.execute(
                    """
                    INSERT INTO sale_items
                        (sale_id, product_id, description, qty, rate, amount)
                    VALUES
                        (?, ?, ?, ?, ?, ?)
                    """,
                    (
                        sale_id,
                        li["product_id"],
                        li["description"],
                        li["qty"],
                        li["rate"],
                        li["amount"],
                    ),
                )

            # Deduct stock atomically (per product total)
            for product_id, qty_total in qty_total_by_product.items():
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

            conn.commit()
        except Exception as e:
            conn.rollback()
            error = str(e)
        finally:
            conn.close()

    if error:
        flash(error, "error")
        return redirect(url_for("sales"))

    if generate_invoice:
        return redirect(url_for("sales_invoice_pdf", id=sale_id))

    flash("Sale saved successfully.", "success")
    flash("Sale saved successfully.", "success")
    return redirect(url_for("sales"))


@app.route("/sales/check-invoice", methods=["GET"])
@login_required
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
@login_required
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
                s.notes,
                s.status
            FROM sales s
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
                s.payment_type,
                s.status
            FROM sales s
            LEFT JOIN customers c ON c.id = s.customer_id
            LEFT JOIN sale_items si ON si.sale_id = s.id
            GROUP BY s.id
            ORDER BY s.invoice_date DESC, s.id DESC
            LIMIT 10
            """
        ).fetchall()
        
    finally:
        conn.close()
    
    return render_template(
        "sales.html",
        customers=[dict(c) for c in customers],
        recent_sales=[dict(r) for r in recent_sales],
        next_invoice_number=get_next_invoice_number(),
        today=date.today().isoformat(),
        edit_mode=True,
        edit_sale=edit_sale,
    )


@app.route("/sales/update/<int:sale_id>", methods=["POST"])
@login_required
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

    error = None

    try:
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
            except Exception:
                error = f"Invalid values in item row {idx + 1}."
                break

            if qty < 0.01:
                error = f"Qty must be at least 0.01 in item row {idx + 1}."
                break
            if rate < 0:
                error = f"Rate cannot be negative in item row {idx + 1}."
                break
            if not description:
                error = f"Description is required in item row {idx + 1}."
                break

            amount = round(qty * rate, 2)
            parsed_items.append(
                {
                    "product_id": product_id,
                    "description": description,
                    "qty": qty,
                    "rate": rate,
                    "amount": amount,
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

        conn = get_connection()
        try:
            conn.execute("BEGIN")

            # Get old sale items to restore stock
            old_items = conn.execute(
                """
                SELECT product_id, qty
                FROM sale_items
                WHERE sale_id = ?
                """,
                (sale_id,),
            ).fetchall()

            # Restore old stock
            old_qty_by_product = defaultdict(float)
            for item in old_items:
                old_qty_by_product[item["product_id"]] += float(item["qty"])

            for product_id, qty_total in old_qty_by_product.items():
                conn.execute(
                    "UPDATE products SET stock_quantity = stock_quantity + ? WHERE id = ?",
                    (qty_total, product_id),
                )

            # Calculate new stock requirements
            new_qty_by_product = defaultdict(float)
            for li in parsed_items:
                new_qty_by_product[li["product_id"]] += li["qty"]

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
            conn.execute(
                """
                UPDATE sales
                SET
                    invoice_number = ?,
                    customer_id = ?,
                    invoice_date = ?,
                    due_date = ?,
                    terms = ?,
                    payment_type = ?,
                    discount_amount = ?,
                    subtotal = ?,
                    grand_total = ?,
                    notes = ?,
                    status = ?,
                    amount_paid = ?,
                    remaining_amount = ?
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
                        (sale_id, product_id, description, qty, rate, amount)
                    VALUES
                        (?, ?, ?, ?, ?, ?)
                    """,
                    (
                        sale_id,
                        li["product_id"],
                        li["description"],
                        li["qty"],
                        li["rate"],
                        li["amount"],
                    ),
                )

            # Deduct new stock
            for product_id, qty_total in new_qty_by_product.items():
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
        
        return jsonify({
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
            "items": [dict(item) for item in items]
        })
    finally:
        conn.close()


@app.route("/sales/by-invoice/<invoice_number>", methods=["GET"])
@login_required
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
@login_required
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
            return Response("Customer not found", status=404)

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


@app.route("/sales/delete/<int:id>", methods=["POST"])
@login_required
def sales_delete(id: int):
    conn = get_connection()
    try:
        conn.execute("BEGIN")

        items = conn.execute(
            """
            SELECT product_id, qty
            FROM sale_items
            WHERE sale_id = ?
            """,
            (id,),
        ).fetchall()

        conn.execute("DELETE FROM sale_items WHERE sale_id = ?", (id,))
        conn.execute("DELETE FROM sales WHERE id = ?", (id,))

        for it in items:
            conn.execute(
                """
                UPDATE products
                SET stock_quantity = stock_quantity + ?
                WHERE id = ?
                """,
                (it["qty"], it["product_id"]),
            )

        conn.commit()
    except Exception:
        conn.rollback()
        flash("Failed to delete sale.", "error")
        return redirect(url_for("sales"))
    finally:
        conn.close()

    flash("Sale deleted successfully.", "success")
    return redirect(url_for("sales"))


@app.route("/reports")
@login_required
def reports():
    return render_template("reports.html")


def _sales_filters_from_request():
    date_from = (request.args.get("date_from") or "").strip()
    date_to = (request.args.get("date_to") or "").strip()
    payment_type = (request.args.get("payment_type") or "all").strip()

    conditions = ["s.customer_id IS NOT NULL"]
    params = []

    if date_from:
        conditions.append("s.invoice_date >= ?")
        params.append(date_from)
    if date_to:
        conditions.append("s.invoice_date <= ?")
        params.append(date_to)
    if payment_type and payment_type != "all":
        conditions.append("s.payment_type = ?")
        params.append(payment_type)

    return " AND ".join(conditions), params


@app.route("/reports/by-customer", methods=["GET"])
@login_required
def reports_by_customer():
    where_sql, params = _sales_filters_from_request()

    conn = get_connection()
    try:
        summary = conn.execute(
            f"""
            SELECT 
              c.id as customer_id,
              c.name as customer_name,
              c.area,
              COUNT(s.id) as invoice_count,
              COALESCE(SUM(s.grand_total), 0) 
                as total_revenue,
              COALESCE(SUM(s.remaining_amount), 0) 
                as outstanding,
              MAX(s.invoice_date) as last_sale_date
            FROM customers c
            LEFT JOIN sales s ON s.customer_id = c.id
            WHERE {where_sql}
            GROUP BY c.id, c.name, c.area
            ORDER BY total_revenue DESC
            """
            ,
            params,
        ).fetchall()

        invoices = conn.execute(
            f"""
            SELECT
                s.customer_id,
                s.invoice_number,
                s.invoice_date,
                COALESCE(s.grand_total, 0) AS grand_total,
                s.payment_type,
                s.status
            FROM sales s
            WHERE {where_sql}
            ORDER BY s.invoice_date DESC, s.id DESC
            """
            ,
            params,
        ).fetchall()
    finally:
        conn.close()

    by_customer = {}
    for row in summary:
        by_customer[int(row["customer_id"])] = {
            "customer_id": int(row["customer_id"]),
            "customer_name": row["customer_name"] or "",
            "area": row["area"] or "",
            "invoice_count": int(row["invoice_count"] or 0),
            "total_revenue": float(row["total_revenue"] or 0),
            "outstanding": float(row["outstanding"] or 0),
            "last_sale_date": row["last_sale_date"] or "",
            "invoices": [],
        }

    for inv in invoices:
        cid = int(inv["customer_id"])
        item = {
            "invoice_number": inv["invoice_number"] or "",
            "invoice_date": inv["invoice_date"] or "",
            "grand_total": float(inv["grand_total"] or 0),
            "payment_type": inv["payment_type"] or "",
            "status": inv["status"] or "",
        }
        if cid in by_customer:
            by_customer[cid]["invoices"].append(item)

    return jsonify(list(by_customer.values()))


@app.route("/reports/by-area", methods=["GET"])
@login_required
def reports_by_area():
    where_sql, params = _sales_filters_from_request()

    conn = get_connection()
    try:
        rows = conn.execute(
            f"""
            SELECT
                COALESCE(NULLIF(TRIM(c.area), ''), 'Unspecified') AS area,
                COUNT(DISTINCT c.id) AS customer_count,
                COUNT(DISTINCT s.id) AS invoice_count,
                COALESCE(SUM(s.grand_total), 0) AS total_revenue
            FROM sales s
            JOIN customers c ON c.id = s.customer_id
            WHERE {where_sql}
            GROUP BY area
            ORDER BY area COLLATE NOCASE
            """,
            params,
        ).fetchall()
    finally:
        conn.close()

    return jsonify(
        [
            {
                "area": r["area"] or "",
                "customer_count": int(r["customer_count"] or 0),
                "invoice_count": int(r["invoice_count"] or 0),
                "total_revenue": float(r["total_revenue"] or 0),
            }
            for r in rows
        ]
    )


@app.route("/reports/by-category", methods=["GET"])
@login_required
def reports_by_category():
    # Category reports are driven by sale_items joined to sales.
    date_from = (request.args.get("date_from") or "").strip()
    date_to = (request.args.get("date_to") or "").strip()
    payment_type = (request.args.get("payment_type") or "all").strip()

    conditions = ["s.customer_id IS NOT NULL"]
    params = []
    if date_from:
        conditions.append("s.invoice_date >= ?")
        params.append(date_from)
    if date_to:
        conditions.append("s.invoice_date <= ?")
        params.append(date_to)
    if payment_type and payment_type != "all":
        conditions.append("s.payment_type = ?")
        params.append(payment_type)
    where_sql = " AND ".join(conditions)

    conn = get_connection()
    try:
        rows = conn.execute(
            f"""
            SELECT
                COALESCE(cat.name, 'Uncategorized') AS category_name,
                COALESCE(SUM(si.qty), 0) AS qty_sold,
                COALESCE(SUM(si.amount), 0) AS total_revenue
            FROM sale_items si
            JOIN products p ON p.id = si.product_id
            LEFT JOIN categories cat ON cat.id = p.category_id
            JOIN sales s ON s.id = si.sale_id
            WHERE {where_sql}
            GROUP BY category_name
            ORDER BY category_name COLLATE NOCASE
            """,
            params,
        ).fetchall()
    finally:
        conn.close()

    return jsonify(
        [
            {
                "category_name": r["category_name"] or "",
                "qty_sold": float(r["qty_sold"] or 0),
                "total_revenue": float(r["total_revenue"] or 0),
            }
            for r in rows
        ]
    )


@app.route("/reports/by-product", methods=["GET"])
@login_required
def reports_by_product():
    date_from = (request.args.get("date_from") or "").strip()
    date_to = (request.args.get("date_to") or "").strip()
    payment_type = (request.args.get("payment_type") or "all").strip()

    conditions = ["s.customer_id IS NOT NULL"]
    params = []
    if date_from:
        conditions.append("s.invoice_date >= ?")
        params.append(date_from)
    if date_to:
        conditions.append("s.invoice_date <= ?")
        params.append(date_to)
    if payment_type and payment_type != "all":
        conditions.append("s.payment_type = ?")
        params.append(payment_type)
    where_sql = " AND ".join(conditions)

    conn = get_connection()
    try:
        rows = conn.execute(
            f"""
            SELECT
                p.name AS product_name,
                p.brand AS brand,
                COALESCE(cat.name, 'Uncategorized') AS category,
                COALESCE(SUM(si.qty), 0) AS units_sold,
                COALESCE(SUM(si.amount), 0) AS total_revenue,
                COALESCE(p.stock_quantity, 0) AS current_stock
            FROM sale_items si
            JOIN products p ON p.id = si.product_id
            LEFT JOIN categories cat ON cat.id = p.category_id
            JOIN sales s ON s.id = si.sale_id
            WHERE {where_sql}
            GROUP BY p.id
            ORDER BY p.name COLLATE NOCASE
            """,
            params,
        ).fetchall()
    finally:
        conn.close()

    return jsonify(
        [
            {
                "product_name": r["product_name"] or "",
                "brand": r["brand"] or "",
                "category": r["category"] or "",
                "units_sold": float(r["units_sold"] or 0),
                "total_revenue": float(r["total_revenue"] or 0),
                "current_stock": float(r["current_stock"] or 0),
            }
            for r in rows
        ]
    )


def _export_csv_bytes(rows, header):
    buf = io.StringIO()
    writer = csv.writer(buf)
    writer.writerow(header)
    for row in rows:
        writer.writerow(row)
    return buf.getvalue().encode("utf-8")


import io  # used for CSV buffer


@app.route("/reports/export/<type>", methods=["GET"])
@login_required
def reports_export(type: str):
    date_from = (request.args.get("date_from") or "").strip()
    date_to = (request.args.get("date_to") or "").strip()
    payment_type = (request.args.get("payment_type") or "all").strip()

    query = {"date_from": date_from, "date_to": date_to, "payment_type": payment_type}
    qs = {k: v for k, v in query.items() if v}

    # Best-effort year in filename.
    year = None
    for candidate in (date_from, date_to):
        if candidate and len(candidate) >= 4:
            year = candidate[:4]
            break
    if not year:
        year = str(date.today().year)

    if type == "customer":
        where_sql, params = _sales_filters_from_request()
        conn = get_connection()
        try:
            rows = conn.execute(
                f"""
                SELECT
                    c.name AS customer_name,
                    c.area AS area,
                    COUNT(DISTINCT s.id) AS invoice_count,
                    COALESCE(SUM(s.grand_total), 0) AS total_revenue,
                    COALESCE(
                        SUM(
                            CASE
                                WHEN s.payment_type = 'credit' AND s.status = 'unpaid'
                                THEN COALESCE(s.grand_total, 0)
                                ELSE 0
                            END
                        ),
                        0
                    ) AS outstanding,
                    MAX(s.invoice_date) AS last_sale_date
                FROM sales s
                JOIN customers c ON c.id = s.customer_id
                WHERE {where_sql}
                GROUP BY c.id
                ORDER BY total_revenue DESC
                """,
                params,
            ).fetchall()
        finally:
            conn.close()

        header = [
            "Customer Name",
            "Area",
            "Total Invoices",
            "Total Revenue",
            "Outstanding",
            "Last Sale Date",
        ]
        csv_rows = [
            [
                r["customer_name"] or "",
                r["area"] or "",
                str(int(r["invoice_count"] or 0)),
                f'{float(r["total_revenue"] or 0):.2f}',
                f'{float(r["outstanding"] or 0):.2f}',
                r["last_sale_date"] or "",
            ]
            for r in rows
        ]

        filename = f"sales_by_customer_{year}.csv"

    elif type == "area":
        where_sql, params = _sales_filters_from_request()
        conn = get_connection()
        try:
            rows = conn.execute(
                f"""
                SELECT
                    COALESCE(NULLIF(TRIM(c.area), ''), 'Unspecified') AS area,
                    COUNT(DISTINCT c.id) AS customer_count,
                    COUNT(DISTINCT s.id) AS invoice_count,
                    COALESCE(SUM(s.grand_total), 0) AS total_revenue
                FROM sales s
                JOIN customers c ON c.id = s.customer_id
                WHERE {where_sql}
                GROUP BY area
                ORDER BY area COLLATE NOCASE
                """,
                params,
            ).fetchall()
        finally:
            conn.close()

        header = ["Area", "Total Customers", "Total Invoices", "Total Revenue"]
        csv_rows = [
            [
                r["area"] or "",
                str(int(r["customer_count"] or 0)),
                str(int(r["invoice_count"] or 0)),
                f'{float(r["total_revenue"] or 0):.2f}',
            ]
            for r in rows
        ]
        filename = f"sales_by_area_{year}.csv"

    elif type == "category":
        # Need category summary query without nested exports.
        date_from = (request.args.get("date_from") or "").strip()
        date_to = (request.args.get("date_to") or "").strip()
        payment_type = (request.args.get("payment_type") or "all").strip()
        conditions = ["s.customer_id IS NOT NULL"]
        params = []
        if date_from:
            conditions.append("s.invoice_date >= ?")
            params.append(date_from)
        if date_to:
            conditions.append("s.invoice_date <= ?")
            params.append(date_to)
        if payment_type and payment_type != "all":
            conditions.append("s.payment_type = ?")
            params.append(payment_type)
        where_sql = " AND ".join(conditions)

        conn = get_connection()
        try:
            rows = conn.execute(
                f"""
                SELECT
                    COALESCE(cat.name, 'Uncategorized') AS category_name,
                    COALESCE(SUM(si.qty), 0) AS qty_sold,
                    COALESCE(SUM(si.amount), 0) AS total_revenue
                FROM sale_items si
                JOIN products p ON p.id = si.product_id
                LEFT JOIN categories cat ON cat.id = p.category_id
                JOIN sales s ON s.id = si.sale_id
                WHERE {where_sql}
                GROUP BY category_name
                ORDER BY category_name COLLATE NOCASE
                """,
                params,
            ).fetchall()
        finally:
            conn.close()

        header = ["Category", "Total Items Sold (Qty)", "Total Revenue"]
        csv_rows = [
            [r["category_name"] or "", f'{float(r["qty_sold"] or 0):.3f}', f'{float(r["total_revenue"] or 0):.2f}']
            for r in rows
        ]
        filename = f"sales_by_category_{year}.csv"

    elif type == "product":
        date_from = (request.args.get("date_from") or "").strip()
        date_to = (request.args.get("date_to") or "").strip()
        payment_type = (request.args.get("payment_type") or "all").strip()
        conditions = ["s.customer_id IS NOT NULL"]
        params = []
        if date_from:
            conditions.append("s.invoice_date >= ?")
            params.append(date_from)
        if date_to:
            conditions.append("s.invoice_date <= ?")
            params.append(date_to)
        if payment_type and payment_type != "all":
            conditions.append("s.payment_type = ?")
            params.append(payment_type)
        where_sql = " AND ".join(conditions)

        conn = get_connection()
        try:
            rows = conn.execute(
                f"""
                SELECT
                    p.name AS product_name,
                    p.brand AS brand,
                    COALESCE(cat.name, 'Uncategorized') AS category,
                    COALESCE(SUM(si.qty), 0) AS units_sold,
                    COALESCE(SUM(si.amount), 0) AS total_revenue,
                    COALESCE(p.stock_quantity, 0) AS current_stock
                FROM sale_items si
                JOIN products p ON p.id = si.product_id
                LEFT JOIN categories cat ON cat.id = p.category_id
                JOIN sales s ON s.id = si.sale_id
                WHERE {where_sql}
                GROUP BY p.id
                ORDER BY p.name COLLATE NOCASE
                """,
                params,
            ).fetchall()
        finally:
            conn.close()

        header = ["#", "Product Name", "Brand", "Category", "Units Sold", "Total Revenue", "Current Stock"]
        csv_rows = []
        for i, r in enumerate(rows, start=1):
            csv_rows.append(
                [
                    str(i),
                    r["product_name"] or "",
                    r["brand"] or "",
                    r["category"] or "",
                    f'{float(r["units_sold"] or 0):.3f}',
                    f'{float(r["total_revenue"] or 0):.2f}',
                    f'{float(r["current_stock"] or 0):.3f}',
                ]
            )
        filename = f"sales_by_product_{year}.csv"

    else:
        return Response("Invalid export type", status=400)

    csv_bytes = _export_csv_bytes(csv_rows, header)
    resp = Response(csv_bytes, mimetype="text/csv")
    resp.headers["Content-Disposition"] = f'attachment; filename="{filename}"'
    return resp


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
