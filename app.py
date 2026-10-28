import os
import json
import sqlite3
import re

import csv

from datetime import date, timedelta

from collections import defaultdict

from database import get_connection, get_next_invoice_number, get_user_by_id, get_user_by_username, get_company, register_company_with_admin, init_db, DB_PATH

import urllib.parse

from flask import Flask, Response, abort, flash, jsonify, redirect, render_template, request, url_for, send_from_directory, session
from flask_login import LoginManager, UserMixin, current_user, login_required, login_user, logout_user
from werkzeug.security import check_password_hash, generate_password_hash
from werkzeug.exceptions import HTTPException
from functools import wraps

from invoice_generator import generate_invoice_pdf
import storage

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "change-this-secret-key-for-local-use")
init_db()

from flask_cors import CORS
CORS(app, resources={r"/api/*": {"origins": "*"}})

from api_routes import api_bp
app.register_blueprint(api_bp, url_prefix='/api')

@app.route("/healthz", methods=["GET"])
def healthz():
    """Health check endpoint for Render, keep-alive monitors, and orchestration."""
    from database import is_postgres_configured
    db_mode = "postgresql" if is_postgres_configured() else "sqlite"
    return jsonify({
        "status": "healthy",
        "app": "Pallo Multi-Tenant SaaS",
        "database": db_mode,
        "storage": storage.get_storage_provider(),
        "version": "1.0.0"
    }), 200

@app.route("/")
def index():
    if current_user.is_authenticated:
        if current_user.role == 'salesman':
            return redirect(url_for("pos"))
        return redirect(url_for("dashboard"))
    return redirect(url_for("login"))

def fetch_resources(uri, rel):
    """Callback to resolve local paths for xhtml2pdf"""
    clean_uri = urllib.parse.unquote(str(uri).strip())
    if '?' in clean_uri:
        clean_uri = clean_uri.split('?')[0]
    if clean_uri.startswith('/static/'):
        return os.path.join(app.root_path, 'static', clean_uri[len('/static/'):])
    elif clean_uri.startswith('static/'):
        return os.path.join(app.root_path, 'static', clean_uri[len('static/'):])
    return clean_uri

@app.route("/brochure/download")
def download_brochure():
    downloads_dir = os.path.join(app.root_path, 'static', 'downloads')
    filename = 'brochure.pdf'
    file_path = os.path.join(downloads_dir, filename)
    if not os.path.exists(file_path):
        return "Brochure is not currently available. Please check back later.", 404
    return send_from_directory(downloads_dir, filename, as_attachment=True, download_name="AK_Distributors_Brochure.pdf")

@app.route("/catalogue")
@app.route("/c/<company_slug>/catalogue")
def public_catalogue(company_slug=None):
    conn = get_connection()
    try:
        if company_slug:
            co = conn.execute("SELECT * FROM companies WHERE slug = ? AND (is_active = 1 OR is_active IS TRUE)", (company_slug,)).fetchone()
            if not co:
                abort(404)
            cid = co["id"]
            company = dict(co)
        else:
            cid = 1
            company = get_company(1)

        warehouses = conn.execute("SELECT id, name FROM warehouses WHERE company_id = ? ORDER BY name", (cid,)).fetchall()
        return render_template("catalogue.html", warehouses=[dict(w) for w in warehouses], current_company=company)
    finally:
        conn.close()

@app.route("/brochure")
@app.route("/c/<company_slug>/brochure")
def public_brochure(company_slug=None):
    from database import get_brochure_products
    conn = get_connection()
    try:
        if company_slug:
            co = conn.execute("SELECT * FROM companies WHERE slug = ? AND (is_active = 1 OR is_active IS TRUE)", (company_slug,)).fetchone()
            if not co:
                abort(404)
            cid = co["id"]
            company = dict(co)
        else:
            cid = 1
            company = get_company(1)

        products = get_brochure_products(cid)[:250]
        brands = {}
        for p in products:
            b = p.get('brand') or 'Other'
            if b not in brands:
                brands[b] = []
            brands[b].append(p)

        return render_template("brochure.html", brands=brands, brand_logos={}, company=company)
    finally:
        conn.close()

@app.route("/c/<company_slug>/brochure/download")
def download_tenant_brochure(company_slug):
    conn = get_connection()
    try:
        co = conn.execute("SELECT * FROM companies WHERE slug = ? AND (is_active = 1 OR is_active IS TRUE)", (company_slug,)).fetchone()
        if not co:
            abort(404)
        cid = co["id"]
        company = dict(co)
    finally:
        conn.close()

    downloads_dir = os.path.join(app.root_path, 'static', 'downloads')
    filename = f'brochure_company_{cid}.pdf' if cid != 1 else 'brochure.pdf'
    file_path = os.path.join(downloads_dir, filename)
    if not os.path.exists(file_path):
        if os.path.exists(os.path.join(downloads_dir, 'brochure.pdf')):
            filename = 'brochure.pdf'
        else:
            return "Brochure is not currently available. Please check back later.", 404
    return send_from_directory(downloads_dir, filename, as_attachment=True, download_name=f"{company['slug']}_Brochure.pdf")

login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = "login"
login_manager.login_message = None


class User(UserMixin):
    def __init__(self, db_id: int, username: str, role: str = 'admin', warehouse_id: int = None, company_id: int = 1):
        self.id = db_id
        self.username = username
        self.role = role
        self.warehouse_id = warehouse_id
        self.company_id = company_id if company_id is not None else 1


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

    # Check user account activation
    is_active = row.get("is_active", 1)
    if is_active in (0, False):
        return None

    role = row.get("role", "admin")
    warehouse_id = row.get("warehouse_id")
    company_id = row.get("company_id")
    if company_id is None:
        company_id = 1

    # Superadmin tenant switcher override (session-driven)
    if role == "superadmin":
        try:
            from flask import has_request_context, session
            if has_request_context():
                switched_cid = session.get("active_company_id")
                if switched_cid:
                    company_id = int(switched_cid)
        except Exception:
            pass

    # Enforce company soft-deactivation (ADR 0004); superadmins bypass company pause
    if role != "superadmin":
        company = get_company(company_id)
        if company and not company.get("is_active", True):
            return None

    return User(row["id"], row["username"], role, warehouse_id, company_id)


def superadmin_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not current_user.is_authenticated:
            return redirect(url_for('login'))
        if current_user.role != 'superadmin':
            return redirect(url_for('dashboard'))
        return f(*args, **kwargs)
    return decorated_function


def company_admin_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not current_user.is_authenticated:
            return redirect(url_for('login'))
        if current_user.role not in ('admin', 'superadmin'):
            return redirect(url_for('pos'))
        return f(*args, **kwargs)
    return decorated_function


def admin_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not current_user.is_authenticated:
            return redirect(url_for('login'))
        if current_user.role not in ('admin', 'superadmin'):
            return redirect(url_for('pos'))
        return f(*args, **kwargs)
    return decorated_function


@app.context_processor
def inject_pallo_context():
    """
    Inject multi-tenant company context and SaaS brand tokens into all Jinja2 templates.
    """
    company = None
    if current_user.is_authenticated:
        cid = getattr(current_user, "company_id", 1) or 1
        company = get_company(cid)
    if not company:
        company = get_company(1)

    is_superadmin = bool(current_user.is_authenticated and current_user.role == "superadmin")
    all_companies = []
    active_switched_company_id = None
    if is_superadmin:
        try:
            from flask import session
            active_switched_company_id = session.get("active_company_id")
            conn = get_connection()
            try:
                all_companies = [dict(c) for c in conn.execute("SELECT id, name, slug, is_active FROM companies ORDER BY name ASC").fetchall()]
            finally:
                conn.close()
        except Exception:
            pass

    return {
        "current_company": company,
        "app_name": "Pallo",
        "is_superadmin": is_superadmin,
        "all_companies": all_companies,
        "active_switched_company_id": active_switched_company_id,
    }

@app.template_filter("format_rate")
def format_rate_filter(val):
    try:
        v = float(val or 0)
        if abs(v - round(v, 2)) < 1e-5:
            return f"{v:.2f}"
        return f"{v:.4f}"
    except Exception:
        return "0.00"

@app.template_filter("format_qty")
def format_qty_filter(val):
    try:
        v = float(val or 0)
        if abs(v - round(v)) < 1e-5:
            return f"{int(round(v))}"
        return f"{v:.3f}".rstrip('0').rstrip('.')
    except Exception:
        return "0"

@app.template_filter("brand_logo_filename")
def brand_logo_filename_filter(val):
    from database import get_brand_logo_filename
    return get_brand_logo_filename(val)





@app.route("/login", methods=["GET", "POST"])
def login():
    if current_user.is_authenticated:
        if current_user.role == 'superadmin':
            return redirect(url_for("superadmin_dashboard") if "superadmin_dashboard" in app.view_functions else url_for("dashboard"))
        if current_user.role == 'salesman':
            return redirect(url_for("pos"))
        return redirect(url_for("dashboard"))
    if request.method == "POST":
        username = (request.form.get("username") or "").strip()
        password = request.form.get("password") or ""
        row = get_user_by_username(username)
        if row is not None and check_password_hash(row["password_hash"], password):
            is_active = row.get("is_active", 1)
            if is_active in (0, False):
                return render_template(
                    "login.html",
                    error="Account is disabled. Please contact the administrator.",
                )

            role = row.get("role", "admin")
            warehouse_id = row.get("warehouse_id")
            company_id = row.get("company_id") or 1

            # Enforce company soft-deactivation (ADR 0004); superadmins bypass company pause
            if role != "superadmin":
                company = get_company(company_id)
                if company and not company.get("is_active", True):
                    return render_template(
                        "login.html",
                        error="Your company account has been paused or suspended. Please contact support.",
                    )

            user_obj = User(row["id"], row["username"], role, warehouse_id, company_id)
            login_user(user_obj, remember=True)
            next_url = request.args.get("next")
            if next_url and next_url.startswith("/"):
                return redirect(next_url)
            if user_obj.role == 'superadmin':
                return redirect(url_for("superadmin_dashboard") if "superadmin_dashboard" in app.view_functions else url_for("dashboard"))
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


@app.route("/register", methods=["GET", "POST"])
def register():
    if current_user.is_authenticated:
        return redirect(url_for("dashboard"))

    if request.method == "POST":
        company_name = (request.form.get("company_name") or "").strip()
        username = (request.form.get("username") or "").strip()
        password = request.form.get("password") or ""
        confirm_password = request.form.get("confirm_password") or ""
        currency = (request.form.get("currency") or "$").strip()

        # Input validation
        if len(company_name) < 2:
            return render_template(
                "register.html",
                error="Business / Company name must be at least 2 characters long.",
                company_name=company_name,
                username=username,
                currency=currency,
            )

        if len(username) < 3:
            return render_template(
                "register.html",
                error="Username must be at least 3 characters long.",
                company_name=company_name,
                username=username,
                currency=currency,
            )

        # Global uniqueness check per ADR 0002
        existing_user = get_user_by_username(username)
        if existing_user is not None:
            return render_template(
                "register.html",
                error="That username is already taken. Please choose another username.",
                company_name=company_name,
                username=username,
                currency=currency,
            )

        if len(password) < 6:
            return render_template(
                "register.html",
                error="Password must be at least 6 characters long.",
                company_name=company_name,
                username=username,
                currency=currency,
            )

        if password != confirm_password:
            return render_template(
                "register.html",
                error="Passwords do not match.",
                company_name=company_name,
                username=username,
                currency=currency,
            )

        try:
            password_hash = generate_password_hash(password, method="pbkdf2:sha256")
            prefix = company_name[:3].upper() + "-" if len(company_name) >= 3 else "INV-"
            company_id, user_id = register_company_with_admin(
                company_name=company_name,
                admin_username=username,
                admin_password_hash=password_hash,
                currency=currency,
                invoice_prefix=prefix,
            )

            # Auto-login newly registered company owner
            user_obj = User(
                db_id=user_id,
                username=username,
                role="admin",
                warehouse_id=None,
                company_id=company_id,
            )
            login_user(user_obj, remember=True)
            flash(f"Welcome to Pallo! Your company workspace '{company_name}' has been created.", "success")
            return redirect(url_for("dashboard"))

        except Exception as e:
            app.logger.error("Registration error: %s", e)
            return render_template(
                "register.html",
                error="An unexpected error occurred while creating your workspace. Please try again.",
                company_name=company_name,
                username=username,
                currency=currency,
            )

    return render_template("register.html")


import traceback

@app.errorhandler(Exception)
def handle_exception(e):
    # pass through HTTP errors
    if isinstance(e, HTTPException):
        return e
    # now you're handling non-HTTP exceptions only
    tb = traceback.format_exc()
    return f"<h1>Internal Server Error</h1><pre>{tb}</pre>", 500

@app.route("/admin/brochure/settings", methods=["GET", "POST"])
@admin_required
def brochure_settings():
    from database import get_connection
    cid = current_user.company_id if current_user.is_authenticated else 1
    conn = get_connection()
    try:
        if request.method == "POST":
            # Reset all for current company
            conn.execute("UPDATE brands SET show_in_brochure = 0 WHERE company_id = ?", (cid,))
            conn.execute("UPDATE products SET show_in_brochure = 0 WHERE company_id = ?", (cid,))
            
            # Get selected brands and products
            selected_brands = request.form.getlist("brands")
            selected_products = request.form.getlist("products")
            
            for b_id in selected_brands:
                conn.execute("UPDATE brands SET show_in_brochure = 1 WHERE id = ? AND company_id = ?", (b_id, cid))
            for p_id in selected_products:
                conn.execute("UPDATE products SET show_in_brochure = 1 WHERE id = ? AND company_id = ?", (p_id, cid))
                
            conn.commit()
            flash("Brochure settings updated successfully.", "success")
            return redirect(url_for("brochure_settings"))
            
        brands = conn.execute("SELECT id, name, show_in_brochure FROM brands WHERE company_id = ? ORDER BY name", (cid,)).fetchall()
        
        # We want to group products by brand to make the UI easier
        products_by_brand = {}
        
        products = conn.execute("SELECT id, name, brand, show_in_brochure FROM products WHERE company_id = ? ORDER BY name", (cid,)).fetchall()
        for p in products:
            b = p['brand'] or 'Uncategorized'
            if b not in products_by_brand:
                products_by_brand[b] = []
            products_by_brand[b].append(p)
            
        return render_template("brochure_settings.html", brands=brands, products_by_brand=products_by_brand)
    finally:
        conn.close()

@app.route("/favicon.ico")
def favicon():
    from flask import send_from_directory
    return send_from_directory(os.path.join(app.root_path, "static"), "favicon.ico", mimetype="image/vnd.microsoft.icon")

@app.route("/admin/brochure/regenerate", methods=["GET", "POST"])
@admin_required
def regenerate_brochure():
    from database import get_brochure_products, get_brand_logo_filename
    from xhtml2pdf import pisa
    from PIL import Image
    from io import BytesIO
    import os, urllib.parse, hashlib, requests
    
    cache_dir = os.path.join(app.root_path, 'static', 'brochure_cache')
    os.makedirs(cache_dir, exist_ok=True)
    products_dir = os.path.join(app.root_path, 'static', 'uploads', 'products')

    def get_optimized_image(url):
        if not url:
            return None
            
        clean_url = urllib.parse.unquote(str(url).strip())
        if '?' in clean_url:
            clean_url = clean_url.split('?')[0]
            
        # External URL support
        if clean_url.startswith(('http://', 'https://')):
            try:
                cache_key = hashlib.md5(clean_url.encode('utf-8')).hexdigest() + '.jpg'
                cached_path = os.path.join(cache_dir, cache_key)
                cached_url = '/static/brochure_cache/' + cache_key
                if os.path.exists(cached_path) and os.path.getsize(cached_path) > 0:
                    return cached_url
                r = requests.get(clean_url, timeout=5)
                if r.status_code == 200:
                    img = Image.open(BytesIO(r.content))
                    if hasattr(img, 'is_animated') and img.is_animated:
                        img.seek(0)
                    if img.mode in ('RGBA', 'LA') or ('transparency' in img.info):
                        rgba = img.convert('RGBA')
                        bg = Image.new('RGB', rgba.size, (255, 255, 255))
                        bg.paste(rgba, mask=rgba.split()[-1])
                        img = bg
                    elif img.mode != 'RGB':
                        img = img.convert('RGB')
                    img.thumbnail((300, 300), Image.Resampling.LANCZOS)
                    img.save(cached_path, 'JPEG', quality=65, optimize=True)
                    return cached_url
            except Exception as e:
                print(f"[!] External image fetch failed for {clean_url}: {e}")
                return None

        # Local path resolution
        if clean_url.startswith('/static/'):
            rel = clean_url[8:]
        elif clean_url.startswith('static/'):
            rel = clean_url[7:]
        elif clean_url.startswith('/'):
            rel = clean_url[1:]
        else:
            rel = clean_url

        candidates = [
            os.path.join(app.root_path, 'static', rel),
            os.path.join(app.root_path, rel),
            os.path.join(products_dir, os.path.basename(rel))
        ]
        
        abs_path = None
        for c in candidates:
            if os.path.exists(c) and os.path.isfile(c):
                abs_path = c
                break
                
        # Fallback: case-insensitive match or alternative extension in products_dir
        if not abs_path and os.path.exists(products_dir):
            base_name = os.path.basename(rel)
            stem, _ = os.path.splitext(base_name)
            for f in os.listdir(products_dir):
                f_stem, _ = os.path.splitext(f)
                if f.lower() == base_name.lower() or f_stem.lower() == stem.lower():
                    abs_path = os.path.join(products_dir, f)
                    break

        if not abs_path or not os.path.exists(abs_path):
            return None

        try:
            mtime = os.path.getmtime(abs_path)
            cache_key = hashlib.md5((abs_path + str(mtime)).encode('utf-8')).hexdigest() + '.jpg'
            cached_path = os.path.join(cache_dir, cache_key)
            cached_url = '/static/brochure_cache/' + cache_key
            
            if os.path.exists(cached_path) and os.path.getsize(cached_path) > 0:
                return cached_url
                
            with Image.open(abs_path) as img:
                if hasattr(img, 'is_animated') and img.is_animated:
                    img.seek(0)
                if img.mode in ('RGBA', 'LA') or ('transparency' in img.info):
                    rgba = img.convert('RGBA')
                    bg = Image.new('RGB', rgba.size, (255, 255, 255))
                    bg.paste(rgba, mask=rgba.split()[-1])
                    img = bg
                elif img.mode != 'RGB':
                    img = img.convert('RGB')
                img.thumbnail((300, 300), Image.Resampling.LANCZOS)
                img.save(cached_path, 'JPEG', quality=65, optimize=True)
                return cached_url
        except Exception as e:
            print(f"[!] Error optimizing image {abs_path}: {e}")
            return None

    cid = current_user.company_id if current_user.is_authenticated else 1
    company = get_company(cid)
    products = get_brochure_products(cid)[:250]
    brands = {}
    brand_logos = {}
    
    for p in products:
        p['image_url'] = get_optimized_image(p.get('image_url'))
            
        b = p.get('brand') or 'Other'
        if b not in brands:
            brands[b] = []
            logo_name = get_brand_logo_filename(b)
            if logo_name:
                optimized_logo = get_optimized_image('/static/logos/brands/' + logo_name)
                brand_logos[b] = optimized_logo if optimized_logo else False
            else:
                brand_logos[b] = False
        brands[b].append(p)
        
    html = render_template('brochure.html', brands=brands, brand_logos=brand_logos, company=company)
    
    downloads_dir = os.path.join(app.root_path, 'static', 'downloads')
    os.makedirs(downloads_dir, exist_ok=True)
    file_path = os.path.join(downloads_dir, 'brochure.pdf' if cid == 1 else f'brochure_company_{cid}.pdf')
    
    with open(file_path, "w+b") as pdf_file:
        pisa_status = pisa.CreatePDF(html, dest=pdf_file, link_callback=fetch_resources)
        
    if pisa_status.err:
        flash("Error generating brochure PDF.", "error")
    else:
        flash("Brochure successfully regenerated.", "success")
        
    return redirect(url_for('brochure_settings'))

@app.route("/help")
@login_required
def help_center():
    lang = request.args.get('lang', 'en')
    if lang == 'ur':
        return render_template("help_ur.html")
    return render_template("help_en.html")

@app.route("/dashboard")
@admin_required
def dashboard():
    warehouse_id_param = request.args.get("warehouse_id")
    if warehouse_id_param == "":
        warehouse_id = None
    elif warehouse_id_param is None and current_user.role == 'admin':
        warehouse_id = None
    else:
        warehouse_id = warehouse_id_param
        
    if current_user.role != 'admin':
        warehouse_id = current_user.warehouse_id
        
    cid = current_user.company_id if hasattr(current_user, "company_id") and current_user.company_id else 1
    conn = get_connection()
    try:
        warehouses = conn.execute("SELECT id, name FROM warehouses WHERE company_id = ? ORDER BY name", (cid,)).fetchall()
        
        # Build conditions
        today = date.today().isoformat()
        now = date.today()
        current_month = f"{now.month:02d}"
        current_year = str(now.year)
        month_pattern = f"{current_year}-{current_month}%"
        
        daily_cond = "company_id = ? AND invoice_date = ?"
        daily_params = [cid, today]
        month_cond = "company_id = ? AND invoice_date LIKE ?"
        month_params = [cid, month_pattern]
        
        if warehouse_id:
            daily_cond += " AND warehouse_id = ?"
            daily_params.append(warehouse_id)
            month_cond += " AND warehouse_id = ?"
            month_params.append(warehouse_id)
            
        # Get today's sales
        daily_revenue_row = conn.execute(
            f'SELECT COALESCE(SUM(grand_total), 0) as total_revenue, COALESCE(SUM(commission_amount), 0) as total_commission FROM sales WHERE {daily_cond}', 
            tuple(daily_params)
        ).fetchone()
        
        # For joins involving sales:
        daily_cost_cond = "s.company_id = ? AND s.invoice_date = ?"
        daily_cost_params = [cid, today]
        month_cost_cond = "s.company_id = ? AND s.invoice_date LIKE ?"
        month_cost_params = [cid, month_pattern]
        
        if warehouse_id:
            daily_cost_cond += " AND s.warehouse_id = ?"
            daily_cost_params.append(warehouse_id)
            month_cost_cond += " AND s.warehouse_id = ?"
            month_cost_params.append(warehouse_id)
            
        daily_cost_row = conn.execute(
            f'''SELECT COALESCE(SUM((si.qty * COALESCE(si.packing_multiplier, 1.0) * si.cost_price) + COALESCE(si.commission_amount, 0)), 0) as total_cost 
               FROM sale_items si 
               JOIN sales s ON si.sale_id = s.id 
               WHERE {daily_cost_cond}''', 
            tuple(daily_cost_params)
        ).fetchone()
        
        daily_revenue = float(daily_revenue_row["total_revenue"] or 0)
        daily_commission = float(daily_revenue_row["total_commission"] or 0)
        daily_cost = float(daily_cost_row["total_cost"] or 0)
        daily_profit = daily_revenue - daily_cost
        
        # Get monthly revenue and cost
        monthly_revenue_row = conn.execute(
            f"SELECT COALESCE(SUM(grand_total), 0) as total_revenue, COALESCE(SUM(commission_amount), 0) as total_commission FROM sales WHERE {month_cond}",
            tuple(month_params)
        ).fetchone()
        monthly_cost_row = conn.execute(
            f'''SELECT COALESCE(SUM((si.qty * COALESCE(si.packing_multiplier, 1.0) * si.cost_price) + COALESCE(si.commission_amount, 0)), 0) as total_cost 
               FROM sale_items si 
               JOIN sales s ON si.sale_id = s.id 
               WHERE {month_cost_cond}''',
            tuple(month_cost_params)
        ).fetchone()
        
        monthly_revenue = float(monthly_revenue_row["total_revenue"] or 0)
        monthly_commission = float(monthly_revenue_row["total_commission"] or 0)
        monthly_cost = float(monthly_cost_row["total_cost"] or 0)
        monthly_profit = monthly_revenue - monthly_cost
        monthly_margin = round((monthly_profit / monthly_revenue * 100), 2) if monthly_revenue > 0 else 0
        
        # Get daily expenses
        daily_expenses_row = conn.execute(
            "SELECT COALESCE(SUM(amount), 0) as total FROM expenses WHERE company_id = ? AND date = ?",
            (cid, today)
        ).fetchone()
        daily_expenses = float(daily_expenses_row["total"] or 0)
        daily_net_profit = daily_profit - daily_expenses

        # Get monthly expenses
        monthly_expenses_row = conn.execute(
            "SELECT COALESCE(SUM(amount), 0) as total FROM expenses WHERE company_id = ? AND date LIKE ?",
            (cid, month_pattern)
        ).fetchone()
        monthly_expenses = float(monthly_expenses_row["total"] or 0)
        monthly_net_profit = monthly_profit - monthly_expenses
        monthly_net_margin = round((monthly_net_profit / monthly_revenue * 100), 2) if monthly_revenue > 0 else 0

        
        recent_sales_cond = "WHERE s.company_id = ?"
        recent_sales_params = [cid]
        if warehouse_id:
            recent_sales_cond += " AND s.warehouse_id = ?"
            recent_sales_params.append(warehouse_id)
            
        recent_sales_rows = conn.execute(
            f'''
            SELECT
                s.id,
                s.invoice_number,
                s.invoice_date,
                c.name AS customer_name,
                s.grand_total,
                s.payment_type,
                s.status,
                (SELECT COALESCE(SUM((si.qty * COALESCE(si.packing_multiplier, 1.0) * si.cost_price) + COALESCE(si.commission_amount, 0)), 0) FROM sale_items si WHERE si.sale_id = s.id) as total_cost
            FROM sales s
            LEFT JOIN customers c ON c.id = s.customer_id
            {recent_sales_cond}
            ORDER BY s.id DESC
            LIMIT 5
            ''', tuple(recent_sales_params)
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
            WHERE s.company_id = ? AND (s.remaining_amount > 0 OR s.status = 'unpaid')
            ORDER BY COALESCE(NULLIF(s.due_date, ''), s.invoice_date) ASC
            LIMIT 10
            """,
            (cid,)
        ).fetchall()
        upcoming_payments = [dict(r) for r in upcoming_payments_rows]
        
        # Get daily sales for the last 30 days
        thirty_days_ago = (date.today() - timedelta(days=30)).isoformat()
        daily_sales_rows = conn.execute(
            """
            SELECT invoice_date, SUM(grand_total) as daily_total
            FROM sales
            WHERE company_id = ? AND invoice_date >= ?
            GROUP BY invoice_date
            ORDER BY invoice_date ASC
            """,
            (cid, thirty_days_ago)
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
        daily_expenses=daily_expenses,
        daily_net_profit=daily_net_profit,
        monthly_expenses=monthly_expenses,
        monthly_net_profit=monthly_net_profit,
        monthly_net_margin=monthly_net_margin,
        recent_sales=recent_sales,
        upcoming_payments=upcoming_payments,
        daily_sales_labels=daily_sales_labels,
        daily_sales_data=daily_sales_data,
        warehouses=warehouses,
        current_warehouse_id=int(warehouse_id) if warehouse_id else None,
    )


@app.route("/inventory")
@login_required
def inventory():
    if current_user.role not in ('admin', 'superadmin', 'warehouse_manager'):
        return redirect(url_for('pos'))

    cid = current_user.company_id
    is_admin = current_user.role in ('admin', 'superadmin')

    brand_filter = request.args.get("brand", "").strip()
    date_from = request.args.get("date_from", "").strip()
    date_to = request.args.get("date_to", "").strip()
    open_only = request.args.get("open_only") == '1'
    stock_filter = request.args.get("stock_filter", "")
    low_stock_threshold = float(request.args.get("low_stock_threshold", 5))
    warehouse_id_param = request.args.get("warehouse_id")
    # Default to None (All Warehouses) if not provided or empty
    if warehouse_id_param == "" or warehouse_id_param is None:
        warehouse_id = None
    else:
        warehouse_id = warehouse_id_param

    if current_user.role != 'admin' and current_user.warehouse_id:
        warehouse_id = current_user.warehouse_id

    conn = get_connection()
    try:
        warehouses = conn.execute("SELECT id, name FROM warehouses WHERE company_id = ? ORDER BY name", (cid,)).fetchall()
        
        if warehouse_id:
            stock_select = "COALESCE((SELECT stock_quantity FROM warehouse_inventory WHERE product_id = p.id AND warehouse_id = ? AND company_id = ?), 0)"
            params = [warehouse_id, cid, cid]
        else:
            stock_select = "COALESCE((SELECT SUM(stock_quantity) FROM warehouse_inventory WHERE product_id = p.id AND company_id = ?), 0)"
            params = [cid, cid]
            
        query = f"""
            SELECT
                p.id,
                p.name,
                p.brand,
                p.unit,
                p.cost_price,
                p.selling_price,
                {stock_select} AS stock_quantity,
                p.image_url,
                p.is_public,
                p.category_id,
                p.created_at,
                p.supplier_id,
                p.is_open,
                c.name AS category_name
            FROM products p
            LEFT JOIN categories c ON (p.category_id = c.id AND c.company_id = p.company_id)
            WHERE p.company_id = ?
        """
        if warehouse_id and current_user.role != 'admin':
            query += " AND EXISTS (SELECT 1 FROM warehouse_inventory wi WHERE wi.product_id = p.id AND wi.warehouse_id = ? AND wi.company_id = ?)"
            params.extend([warehouse_id, cid])
            
        if brand_filter:
            query += " AND p.brand = ?"
            params.append(brand_filter)
        if date_from:
            query += " AND date(p.created_at) >= ?"
            params.append(date_from)
        if date_to:
            query += " AND DATE(p.created_at) <= ?"
            params.append(date_to)
            
        if open_only:
            query += " AND p.is_open = 1"
            
        query += " ORDER BY p.id DESC"
        cur = conn.execute(query, tuple(params))
        products = []
        for row in cur.fetchall():
            d = dict(row)
            sq = float(d['stock_quantity'] or 0)
            if stock_filter == "out_of_stock" and sq > 0:
                continue
            if stock_filter == "low_stock" and (sq <= 0 or sq > low_stock_threshold):
                continue
            if not is_admin:
                d['cost_price'] = None
            products.append(d)

        cur = conn.execute("SELECT COUNT(*) AS total_products FROM products WHERE company_id = ?", (cid,))
        total_products = int(cur.fetchone()["total_products"] or 0)

        if is_admin:
            stock_val_query = """
                SELECT COALESCE(SUM(COALESCE(p.cost_price, 0) * COALESCE(wi.stock_quantity, 0)), 0) AS total_stock_value
                FROM warehouse_inventory wi
                JOIN products p ON wi.product_id = p.id AND p.company_id = wi.company_id
                WHERE wi.company_id = ?
            """
            stock_val_params = [cid]
            if warehouse_id:
                stock_val_query += " AND wi.warehouse_id = ?"
                stock_val_params.append(warehouse_id)
            cur = conn.execute(stock_val_query, tuple(stock_val_params))
            total_stock_value = float(cur.fetchone()["total_stock_value"] or 0)
        else:
            total_stock_value = 0.0

        low_stock_query = "SELECT COALESCE(SUM(CASE WHEN COALESCE(wi.stock_quantity, 0) < 5 THEN 1 ELSE 0 END), 0) AS low_stock_count FROM warehouse_inventory wi WHERE wi.company_id = ?"
        low_stock_params = [cid]
        if warehouse_id:
            low_stock_query += " AND wi.warehouse_id = ?"
            low_stock_params.append(warehouse_id)
        cur = conn.execute(low_stock_query, tuple(low_stock_params))
        low_stock_count = int(cur.fetchone()["low_stock_count"] or 0)

        cur = conn.execute("""
            SELECT c.id, c.name, COUNT(p.id) AS product_count 
            FROM categories c 
            LEFT JOIN products p ON (p.category_id = c.id AND p.company_id = c.company_id)
            WHERE c.company_id = ?
            GROUP BY c.id, c.name 
            ORDER BY c.name COLLATE NOCASE
        """, (cid,))
        categories = [dict(row) for row in cur.fetchall()]

        cur = conn.execute("SELECT id, name FROM suppliers WHERE company_id = ? ORDER BY name COLLATE NOCASE", (cid,))
        suppliers = [dict(row) for row in cur.fetchall()]
    finally:
        conn.close()

    try:
        current_warehouse_id = int(warehouse_id) if warehouse_id else None
    except ValueError:
        current_warehouse_id = None

    return render_template(
        "inventory.html",
        products=products,
        categories=categories,
        suppliers=suppliers,
        total_products=total_products,
        total_stock_value=total_stock_value,
        low_stock_count=low_stock_count,
        warehouses=warehouses,
        current_warehouse_id=current_warehouse_id,
        stock_filter=stock_filter,
        low_stock_threshold=int(low_stock_threshold)
    )


@app.route("/inventory/download_csv")
@login_required
def inventory_download_csv():
    if current_user.role not in ('admin', 'superadmin', 'warehouse_manager'):
        return redirect(url_for('pos'))

    cid = current_user.company_id
    is_admin = current_user.role in ('admin', 'superadmin')

    brand = request.args.get("brand", "").strip()
    date_from = request.args.get("date_from", "").strip()
    date_to = request.args.get("date_to", "").strip()
    
    warehouse_id_param = request.args.get("warehouse_id")
    if warehouse_id_param == "" or warehouse_id_param is None:
        warehouse_id = None
    else:
        warehouse_id = warehouse_id_param

    if current_user.role != 'admin' and current_user.warehouse_id:
        warehouse_id = current_user.warehouse_id
        
    stock_filter = request.args.get("stock_filter", "")
    low_stock_threshold = float(request.args.get("low_stock_threshold", 5))

    conn = get_connection()
    try:
        if warehouse_id:
            stock_select = "COALESCE((SELECT stock_quantity FROM warehouse_inventory WHERE product_id = p.id AND warehouse_id = ? AND company_id = ?), 0)"
            params = [warehouse_id, cid, cid]
        else:
            stock_select = "COALESCE((SELECT SUM(stock_quantity) FROM warehouse_inventory WHERE product_id = p.id AND company_id = ?), 0)"
            params = [cid, cid]
            
        query = f"""
            SELECT
                p.id,
                p.name,
                p.brand,
                p.unit,
                p.cost_price,
                p.selling_price,
                {stock_select} AS stock_quantity,
                p.created_at,
                c.name AS category_name
            FROM products p
            LEFT JOIN categories c ON (p.category_id = c.id AND c.company_id = p.company_id)
            WHERE p.company_id = ?
        """
        if brand:
            query += " AND p.brand = ?"
            params.append(brand)
        if date_from:
            query += " AND date(p.created_at) >= ?"
            params.append(date_from)
        if date_to:
            query += " AND date(p.created_at) <= ?"
            params.append(date_to)
            
        if stock_filter == "out_of_stock":
            query = f"SELECT * FROM ({query}) WHERE stock_quantity <= 0"
        elif stock_filter == "low_stock":
            query = f"SELECT * FROM ({query}) WHERE stock_quantity > 0 AND stock_quantity <= ?"
            params.append(low_stock_threshold)
        else:
            query = f"SELECT * FROM ({query})"
            
        query += " ORDER BY name COLLATE NOCASE"
        cur = conn.execute(query, tuple(params))
        products = [dict(row) for row in cur.fetchall()]
    finally:
        conn.close()

    import io
    import csv
    
    output = io.StringIO()
    writer = csv.writer(output)
    
    total_qty = 0
    total_value = 0.0

    if is_admin:
        writer.writerow([
            "ID", "Date Added", "Product Name", "Brand", "Category", 
            "Cost Price", "Selling Price", "Stock Quantity", "Stock Value"
        ])
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
        writer.writerow([
            "", "", "TOTALS", "", "", "", "", total_qty, f"{total_value:.2f}"
        ])
    else:
        # Redact supplier cost and stock value for non-admin roles
        writer.writerow([
            "ID", "Date Added", "Product Name", "Brand", "Category", 
            "Selling Price", "Stock Quantity"
        ])
        for p in products:
            stock_qty = p["stock_quantity"] if p["stock_quantity"] is not None else 0
            total_qty += stock_qty
            
            writer.writerow([
                p["id"],
                str(p["created_at"] or "")[:10],
                p["name"],
                p["brand"] or "",
                p["category_name"] or "",
                f"{p['selling_price']:.2f}" if p['selling_price'] is not None else "0.00",
                stock_qty
            ])
        writer.writerow([
            "", "", "TOTALS", "", "", "", total_qty
        ])
    
    from datetime import date
    today_str = date.today().strftime("%Y-%m-%d")
    filename = f"inventory_{brand}_{today_str}.csv" if brand else f"inventory_all_{today_str}.csv"
    response = Response(output.getvalue(), mimetype="text/csv")
    response.headers["Content-Disposition"] = f"attachment; filename={filename}"
    return response




@app.route("/inventory/add", methods=["POST"])
@login_required
def inventory_add():
    if current_user.role not in ('admin', 'superadmin', 'warehouse_manager'):
        return redirect(url_for('pos'))

    cid = current_user.company_id
    is_admin = current_user.role in ('admin', 'superadmin')

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
        cost_price = float(request.form.get("cost_price") or 0) if is_admin else 0.0
        selling_price = float(request.form.get("selling_price") or 0)
        stock_quantity = float(request.form.get("stock_quantity") or 0)
    except ValueError:
        return redirect(url_for("inventory"))

    if not product_name or not category_id or not brand:
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
            cur_sup = conn.execute("SELECT id FROM suppliers WHERE name = ? AND company_id = ?", (brand, cid))
            sup_row = cur_sup.fetchone()
            if sup_row:
                supplier_id = sup_row["id"]
            else:
                conn.execute("INSERT INTO suppliers (company_id, name) VALUES (?, ?)", (cid, brand))
                cur_sup = conn.execute("SELECT id FROM suppliers WHERE name = ? AND company_id = ?", (brand, cid))
                supplier_id = cur_sup.fetchone()["id"]
        
        # Check if product already exists within this company
        wid = current_user.warehouse_id or 1
        cur = conn.execute("SELECT id, cost_price, stock_quantity FROM products WHERE LOWER(name) = LOWER(?) AND company_id = ?", (product_name, cid))
        existing = cur.fetchone()
        
        if existing:
            product_id = existing["id"]
            if not is_admin:
                cost_price = float(existing["cost_price"] or 0)
            old_stock_row = conn.execute("SELECT stock_quantity FROM warehouse_inventory WHERE product_id = ? AND warehouse_id = ? AND company_id = ?", (product_id, wid, cid)).fetchone()
            old_stock = float(old_stock_row["stock_quantity"] if old_stock_row else 0)
            
            update_query = """
                UPDATE products
                SET category_id = ?, brand = ?, unit = ?, cost_price = ?, selling_price = ?, supplier_id = ?, is_open = ?
            """
            params = [category_id, brand or None, unit, cost_price, selling_price, supplier_id, is_open]
            
            if created_at:
                update_query += ", created_at = ?"
                params.append(created_at)
                
            if image_url:
                update_query += ", image_url = ?"
                params.append(image_url)
            update_query += " WHERE id = ? AND company_id = ?"
            params.extend([product_id, cid])
            
            conn.execute(update_query, tuple(params))
            
            new_stock = old_stock + stock_quantity
            if stock_quantity > 0:
                conn.execute("""
                    INSERT INTO warehouse_inventory (company_id, product_id, warehouse_id, stock_quantity)
                    VALUES (?, ?, ?, ?)
                    ON CONFLICT(warehouse_id, product_id) DO UPDATE SET stock_quantity = ?
                """, (cid, product_id, wid, new_stock, new_stock))
                conn.execute("""
                    INSERT INTO inventory_history (company_id, product_id, transaction_type, quantity_change, previous_stock, new_stock, reference, warehouse_id)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """, (cid, product_id, 'IN', stock_quantity, old_stock, new_stock, 'Manual Addition', wid))
        else:
            fields = ["company_id", "name", "category_id", "brand", "unit", "cost_price", "selling_price", "is_public", "supplier_id", "is_open"]
            vals = ["?", "?", "?", "?", "?", "?", "?", "?", "?", "?"]
            params_insert = [cid, product_name, category_id, brand or None, unit, cost_price, selling_price, is_public, supplier_id, is_open]
            
            if created_at:
                fields.append("created_at")
                vals.append("?")
                params_insert.append(created_at)
            
            if image_url:
                fields.append("image_url")
                vals.append("?")
                params_insert.append(image_url)
                
            conn.execute(f"INSERT INTO products ({', '.join(fields)}) VALUES ({', '.join(vals)})", tuple(params_insert))
            cur_pid = conn.execute("SELECT id FROM products WHERE LOWER(name) = LOWER(?) AND company_id = ?", (product_name, cid))
            product_id = cur_pid.fetchone()["id"]
            
            if stock_quantity > 0:
                conn.execute("INSERT INTO warehouse_inventory (company_id, product_id, warehouse_id, stock_quantity) VALUES (?, ?, ?, ?)", (cid, product_id, wid, stock_quantity))
                conn.execute("""
                    INSERT INTO inventory_history (company_id, product_id, transaction_type, quantity_change, previous_stock, new_stock, reference, warehouse_id)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """, (cid, product_id, 'IN', stock_quantity, 0, stock_quantity, 'Initial Stock', wid))

        # Keep brands table in sync for the Brand dropdown within this company.
        if brand:
            cur_b = conn.execute("SELECT id FROM brands WHERE LOWER(name) = LOWER(?) AND company_id = ?", (brand, cid))
            if not cur_b.fetchone():
                conn.execute("INSERT INTO brands (company_id, name) VALUES (?, ?)", (cid, brand))

        conn.commit()
    finally:
        conn.close()

    return redirect(url_for("inventory"))


@app.route("/inventory/edit/<int:product_id>", methods=["POST"])
@login_required
def inventory_edit(product_id: int):
    if current_user.role not in ('admin', 'superadmin', 'warehouse_manager'):
        return redirect(url_for('pos'))

    cid = current_user.company_id
    is_admin = current_user.role in ('admin', 'superadmin')

    conn = get_connection()
    try:
        existing = conn.execute("SELECT id, cost_price FROM products WHERE id = ? AND company_id = ?", (product_id, cid)).fetchone()
        if not existing:
            flash("Product not found.", "error")
            return redirect(url_for("inventory"))

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
            # Retain existing cost_price if edited by non-admin to prevent price tampering
            cost_price = float(request.form.get("cost_price") or 0) if is_admin else float(existing["cost_price"] or 0)
            selling_price = float(request.form.get("selling_price") or 0)
        except ValueError:
            return redirect(url_for("inventory"))

        if not product_name or not category_id or not brand:
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

        conn.execute("BEGIN")
        
        # Determine supplier
        if supplier_id:
            try:
                supplier_id = int(supplier_id)
            except ValueError:
                supplier_id = None
        
        if not supplier_id and brand:
            cur_sup = conn.execute("SELECT id FROM suppliers WHERE name = ? AND company_id = ?", (brand, cid))
            sup_row = cur_sup.fetchone()
            if sup_row:
                supplier_id = sup_row["id"]
            else:
                conn.execute("INSERT INTO suppliers (company_id, name) VALUES (?, ?)", (cid, brand))
                cur_sup = conn.execute("SELECT id FROM suppliers WHERE name = ? AND company_id = ?", (brand, cid))
                supplier_id = cur_sup.fetchone()["id"]
        
        update_query = """
            UPDATE products
            SET name = ?, brand = ?, category_id = ?, unit = ?, cost_price = ?, selling_price = ?, is_public = ?, supplier_id = ?, is_open = ?
        """
        params = [product_name, brand, category_id, unit, cost_price, selling_price, is_public, supplier_id, is_open]
        
        if created_at:
            update_query += ", created_at = ?"
            params.append(created_at)

        if image_url:
            update_query += ", image_url = ?"
            params.append(image_url)
        elif remove_image:
            update_query += ", image_url = NULL"
            
        update_query += " WHERE id = ? AND company_id = ?"
        params.extend([product_id, cid])
        
        conn.execute(update_query, tuple(params))
        
        # Keep brands table in sync for the Brand dropdown within this company.
        if brand:
            cur_b = conn.execute("SELECT id FROM brands WHERE LOWER(name) = LOWER(?) AND company_id = ?", (brand, cid))
            if not cur_b.fetchone():
                conn.execute("INSERT INTO brands (company_id, name) VALUES (?, ?)", (cid, brand))

        conn.commit()
    finally:
        conn.close()

    return redirect(url_for("inventory"))



@app.route("/inventory/adjust_stock", methods=["POST"])
@login_required
def inventory_adjust_stock():
    if current_user.role not in ('admin', 'superadmin', 'warehouse_manager'):
        return redirect(url_for('pos'))

    cid = current_user.company_id
    product_id = int(request.form.get("product_id", 0))
    raw_wid = request.form.get("warehouse_id", "").strip()
    try:
        warehouse_id = int(raw_wid) if raw_wid and raw_wid.lower() != 'none' else (current_user.warehouse_id or 1)
    except ValueError:
        warehouse_id = current_user.warehouse_id or 1
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
        prod = conn.execute("SELECT id FROM products WHERE id = ? AND company_id = ?", (product_id, cid)).fetchone()
        if not prod:
            flash("Product not found.", "error")
            return redirect(url_for("inventory"))

        wh = conn.execute("SELECT id FROM warehouses WHERE id = ? AND company_id = ?", (warehouse_id, cid)).fetchone()
        if not wh:
            flash("Warehouse not found.", "error")
            return redirect(url_for("inventory"))

        old_stock_row = conn.execute(
            "SELECT stock_quantity FROM warehouse_inventory WHERE product_id = ? AND warehouse_id = ? AND company_id = ?",
            (product_id, warehouse_id, cid)
        ).fetchone()
        old_stock = float(old_stock_row["stock_quantity"]) if old_stock_row and old_stock_row["stock_quantity"] is not None else 0.0

        if old_stock != new_stock:
            conn.execute(
                """
                INSERT INTO warehouse_inventory (company_id, product_id, warehouse_id, stock_quantity)
                VALUES (?, ?, ?, ?)
                ON CONFLICT(warehouse_id, product_id) DO UPDATE SET stock_quantity = ?
                """,
                (cid, product_id, warehouse_id, new_stock, new_stock)
            )
            
            adjustment = new_stock - old_stock
            conn.execute(
                """
                INSERT INTO inventory_history (company_id, product_id, transaction_type, quantity_change, previous_stock, new_stock, reference, warehouse_id)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (cid, product_id, "Manual Adjustment", adjustment, old_stock, new_stock, None, warehouse_id)
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


@app.route("/inventory/transfer/new", methods=["GET"])
@admin_required
def new_inventory_transfer():
    cid = current_user.company_id if hasattr(current_user, "company_id") and current_user.company_id else 1
    conn = get_connection()
    try:
        warehouses = [dict(row) for row in conn.execute("SELECT id, name FROM warehouses WHERE company_id = ? ORDER BY name", (cid,)).fetchall()]
        products = [dict(row) for row in conn.execute("SELECT id, name, unit, cost_price, selling_price FROM products WHERE company_id = ? ORDER BY name ASC", (cid,)).fetchall()]
    finally:
        conn.close()
    
    preselect_product = request.args.get("product_id", "")
    return render_template("inventory_transfer_new.html", warehouses=warehouses, products=products, preselect_product=preselect_product)

@app.route("/inventory/transfer", methods=["POST"])
@admin_required
def inventory_transfer():
    cid = current_user.company_id if hasattr(current_user, "company_id") and current_user.company_id else 1
    data = request.json
    if not data:
        return jsonify({"ok": False, "error": "Invalid JSON payload"}), 400
        
    source_wid = int(data.get("source_warehouse_id", 0))
    dest_wid = int(data.get("destination_warehouse_id", 0))
    notes = data.get("notes", "").strip()
    items = data.get("items", [])

    if source_wid <= 0 or dest_wid <= 0 or not items:
        return jsonify({"ok": False, "error": "Invalid request for stock transfer."}), 400
        
    if source_wid == dest_wid:
        return jsonify({"ok": False, "error": "Source and destination warehouses must be different."}), 400

    conn = get_connection()
    try:
        # Validate that both warehouses belong to tenant's company
        valid_warehouses = conn.execute("SELECT id FROM warehouses WHERE id IN (?, ?) AND company_id = ?", (source_wid, dest_wid, cid)).fetchall()
        if len(valid_warehouses) < 2:
            return jsonify({"ok": False, "error": "One or both selected warehouses are invalid or unauthorized."}), 400

        conn.execute("BEGIN")
        cursor = conn.execute(
            "INSERT INTO inventory_transfers (source_warehouse_id, destination_warehouse_id, notes, company_id) VALUES (?, ?, ?, ?)",
            (source_wid, dest_wid, notes, cid)
        )
        transfer_id = cursor.lastrowid
        
        for item in items:
            product_id = int(item.get("product_id", 0))
            quantity = float(item.get("quantity", 0))
            
            if product_id <= 0 or quantity <= 0:
                conn.execute("ROLLBACK")
                return jsonify({"ok": False, "error": "Invalid product or quantity."}), 400

            # Verify product belongs to company
            prod_check = conn.execute("SELECT id, name FROM products WHERE id = ? AND company_id = ?", (product_id, cid)).fetchone()
            if not prod_check:
                conn.execute("ROLLBACK")
                return jsonify({"ok": False, "error": f"Product ID {product_id} is invalid or unauthorized."}), 400

            # Check source stock
            source_stock_row = conn.execute("SELECT stock_quantity FROM warehouse_inventory WHERE product_id = ? AND warehouse_id = ? AND company_id = ?", (product_id, source_wid, cid)).fetchone()
            source_stock = float(source_stock_row["stock_quantity"]) if source_stock_row else 0.0
            
            if (source_stock - quantity) < -1e-5:
                conn.execute("ROLLBACK")
                return jsonify({"ok": False, "error": f"Insufficient stock for product {prod_check['name']} in source warehouse. Available: {source_stock}"}), 400

            # Check destination stock
            dest_stock_row = conn.execute("SELECT stock_quantity FROM warehouse_inventory WHERE product_id = ? AND warehouse_id = ? AND company_id = ?", (product_id, dest_wid, cid)).fetchone()
            dest_stock = float(dest_stock_row["stock_quantity"]) if dest_stock_row else 0.0

            # Execute transfer
            new_source_stock = round(source_stock - quantity, 4)
            new_dest_stock = round(dest_stock + quantity, 4)

            conn.execute("UPDATE warehouse_inventory SET stock_quantity = ? WHERE product_id = ? AND warehouse_id = ? AND company_id = ?", (new_source_stock, product_id, source_wid, cid))
            conn.execute(
                "INSERT INTO warehouse_inventory (product_id, warehouse_id, stock_quantity, company_id) VALUES (?, ?, ?, ?) ON CONFLICT(warehouse_id, product_id) DO UPDATE SET stock_quantity = ?",
                (product_id, dest_wid, new_dest_stock, cid, new_dest_stock)
            )

            # Insert into transfer items
            conn.execute(
                "INSERT INTO inventory_transfer_items (transfer_id, product_id, quantity, company_id) VALUES (?, ?, ?, ?)",
                (transfer_id, product_id, round(quantity, 4), cid)
            )

            # Log history
            ref_note = f"Transfer to Warehouse {dest_wid}"
            if notes:
                ref_note += f" ({notes})"
                
            conn.execute(
                "INSERT INTO inventory_history (product_id, transaction_type, quantity_change, previous_stock, new_stock, reference, warehouse_id, company_id) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                (product_id, "Transfer Out", -quantity, source_stock, new_source_stock, ref_note, source_wid, cid)
            )
            
            ref_note_in = f"Transfer from Warehouse {source_wid}"
            if notes:
                ref_note_in += f" ({notes})"
                
            conn.execute(
                "INSERT INTO inventory_history (product_id, transaction_type, quantity_change, previous_stock, new_stock, reference, warehouse_id, company_id) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                (product_id, "Transfer In", quantity, dest_stock, new_dest_stock, ref_note_in, dest_wid, cid)
            )

        conn.commit()
        return jsonify({"ok": True})
    except Exception as e:
        print(f"Error transferring stock: {e}")
        return jsonify({"ok": False, "error": "Failed to transfer stock due to a server error."}), 500
    finally:
        conn.close()

@app.route("/inventory/transfer/edit/<int:transfer_id>", methods=["GET"])
@admin_required
def edit_inventory_transfer(transfer_id):
    cid = current_user.company_id if hasattr(current_user, "company_id") and current_user.company_id else 1
    conn = get_connection()
    try:
        transfer = conn.execute("SELECT * FROM inventory_transfers WHERE id = ? AND company_id = ?", (transfer_id, cid)).fetchone()
        if not transfer:
            return redirect(url_for("inventory_transfers"))
            
        items = conn.execute("SELECT * FROM inventory_transfer_items WHERE transfer_id = ? AND company_id = ?", (transfer_id, cid)).fetchall()
        
        warehouses = [dict(row) for row in conn.execute("SELECT id, name FROM warehouses WHERE company_id = ? ORDER BY name", (cid,)).fetchall()]
        products = [dict(row) for row in conn.execute("SELECT id, name, unit, cost_price, selling_price FROM products WHERE company_id = ? ORDER BY name ASC", (cid,)).fetchall()]
        
        return render_template("inventory_transfer_new.html", 
                               warehouses=warehouses, 
                               products=products, 
                               edit_transfer=dict(transfer), 
                               edit_items=[dict(i) for i in items])
    finally:
        conn.close()

@app.route("/inventory/transfer/edit/<int:transfer_id>", methods=["POST"])
@admin_required
def process_edit_inventory_transfer(transfer_id):
    cid = current_user.company_id if hasattr(current_user, "company_id") and current_user.company_id else 1
    data = request.json
    if not data:
        return jsonify({"ok": False, "error": "Invalid JSON payload"}), 400
        
    new_source_wid = int(data.get("source_warehouse_id", 0))
    new_dest_wid = int(data.get("destination_warehouse_id", 0))
    notes = data.get("notes", "").strip()
    new_items = data.get("items", [])

    if new_source_wid <= 0 or new_dest_wid <= 0 or not new_items:
        return jsonify({"ok": False, "error": "Invalid request for stock transfer."}), 400
        
    if new_source_wid == new_dest_wid:
        return jsonify({"ok": False, "error": "Source and destination warehouses must be different."}), 400

    conn = get_connection()
    try:
        # Validate warehouses belong to company
        valid_warehouses = conn.execute("SELECT id FROM warehouses WHERE id IN (?, ?) AND company_id = ?", (new_source_wid, new_dest_wid, cid)).fetchall()
        if len(valid_warehouses) < 2:
            return jsonify({"ok": False, "error": "One or both selected warehouses are invalid or unauthorized."}), 400

        conn.execute("BEGIN")
        
        old_transfer = conn.execute("SELECT * FROM inventory_transfers WHERE id = ? AND company_id = ?", (transfer_id, cid)).fetchone()
        if not old_transfer:
            conn.execute("ROLLBACK")
            return jsonify({"ok": False, "error": "Transfer not found."}), 404
            
        old_source_wid = old_transfer["source_warehouse_id"]
        old_dest_wid = old_transfer["destination_warehouse_id"]
        
        old_items = conn.execute("SELECT * FROM inventory_transfer_items WHERE transfer_id = ? AND company_id = ?", (transfer_id, cid)).fetchall()
        
        stock_changes = defaultdict(float)
        
        # 1. Reverse the old transfer
        for item in old_items:
            pid = item["product_id"]
            qty = item["quantity"]
            stock_changes[(old_source_wid, pid)] += qty
            stock_changes[(old_dest_wid, pid)] -= qty
            
        # 2. Apply the new transfer
        for item in new_items:
            pid = int(item.get("product_id", 0))
            qty = float(item.get("quantity", 0))
            if pid <= 0 or qty <= 0:
                conn.execute("ROLLBACK")
                return jsonify({"ok": False, "error": "Invalid product or quantity."}), 400
            # Validate product belongs to company
            p_check = conn.execute("SELECT id FROM products WHERE id = ? AND company_id = ?", (pid, cid)).fetchone()
            if not p_check:
                conn.execute("ROLLBACK")
                return jsonify({"ok": False, "error": f"Product ID {pid} is invalid or unauthorized."}), 400
            stock_changes[(new_source_wid, pid)] -= qty
            stock_changes[(new_dest_wid, pid)] += qty
            
        # 3. Apply changes and validate
        for (wid, pid), net_change in stock_changes.items():
            if net_change == 0:
                continue
                
            cur_stock_row = conn.execute(
                "SELECT stock_quantity, p.name FROM warehouse_inventory wi JOIN products p ON p.id = wi.product_id WHERE wi.product_id = ? AND wi.warehouse_id = ? AND wi.company_id = ?",
                (pid, wid, cid)
            ).fetchone()
            
            if not cur_stock_row and net_change < 0:
                conn.execute("ROLLBACK")
                return jsonify({"ok": False, "error": f"Insufficient stock for product ID {pid} in warehouse {wid}."}), 400
                
            cur_stock = cur_stock_row["stock_quantity"] if cur_stock_row else 0.0
            prod_name = cur_stock_row["name"] if cur_stock_row else f"Product {pid}"
            
            new_stock = cur_stock + net_change
            if new_stock < 0 and abs(new_stock) > 1e-9:
                conn.execute("ROLLBACK")
                return jsonify({"ok": False, "error": f"Insufficient stock for {prod_name} in warehouse {wid}. Need {-net_change}, have {cur_stock}."}), 400
                
            if cur_stock_row:
                conn.execute("UPDATE warehouse_inventory SET stock_quantity = ? WHERE product_id = ? AND warehouse_id = ? AND company_id = ?", (new_stock, pid, wid, cid))
            else:
                conn.execute("INSERT INTO warehouse_inventory (product_id, warehouse_id, stock_quantity, company_id) VALUES (?, ?, ?, ?) ON CONFLICT(warehouse_id, product_id) DO UPDATE SET stock_quantity = ?", (pid, wid, new_stock, cid, new_stock))
                
            trans_type = "Transfer Edit In" if net_change > 0 else "Transfer Edit Out"
            ref = f"Edit Transfer #{transfer_id}"
            conn.execute("INSERT INTO inventory_history (product_id, transaction_type, quantity_change, previous_stock, new_stock, reference, warehouse_id, company_id) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                         (pid, trans_type, net_change, cur_stock, new_stock, ref, wid, cid))
                         
        # 4. Update the transfer records
        conn.execute("UPDATE inventory_transfers SET source_warehouse_id = ?, destination_warehouse_id = ?, notes = ? WHERE id = ? AND company_id = ?", (new_source_wid, new_dest_wid, notes, transfer_id, cid))
        
        conn.execute("DELETE FROM inventory_transfer_items WHERE transfer_id = ? AND company_id = ?", (transfer_id, cid))
        for item in new_items:
            conn.execute("INSERT INTO inventory_transfer_items (transfer_id, product_id, quantity, company_id) VALUES (?, ?, ?, ?)", (transfer_id, int(item["product_id"]), float(item["quantity"]), cid))
            
        conn.commit()
        return jsonify({"ok": True})
    except Exception as e:
        conn.execute("ROLLBACK")
        print(f"Error editing stock transfer: {e}")
        return jsonify({"ok": False, "error": "Failed to edit stock transfer due to a server error."}), 500
    finally:
        conn.close()

@app.route("/inventory/transfers", methods=["GET"])
@admin_required
def inventory_transfers():
    cid = current_user.company_id if hasattr(current_user, "company_id") and current_user.company_id else 1
    conn = get_connection()
    try:
        transfers_raw = conn.execute("""
            SELECT 
                it.id,
                it.created_at AS transfer_date,
                it.notes,
                w1.name AS source_warehouse,
                w2.name AS destination_warehouse,
                it.source_warehouse_id,
                it.destination_warehouse_id
            FROM inventory_transfers it
            LEFT JOIN warehouses w1 ON it.source_warehouse_id = w1.id
            LEFT JOIN warehouses w2 ON it.destination_warehouse_id = w2.id
            WHERE it.company_id = ?
            ORDER BY it.id DESC
        """, (cid,)).fetchall()
        
        transfers = []
        for t in transfers_raw:
            t_dict = dict(t)
            items_raw = conn.execute("""
                SELECT 
                    iti.quantity,
                    p.name AS product_name,
                    p.id AS product_id
                FROM inventory_transfer_items iti
                JOIN products p ON p.id = iti.product_id
                WHERE iti.transfer_id = ? AND iti.company_id = ?
            """, (t["id"], cid)).fetchall()
            items_list = [dict(i) for i in items_raw]
            t_dict["items"] = items_list
            t_dict["total_items_count"] = len(items_list)
            t_dict["total_units"] = sum(float(i.get("quantity") or 0) for i in items_list)
            transfers.append(t_dict)
            
        return render_template("inventory_transfers.html", transfers=transfers)
    finally:
        conn.close()

@app.route("/inventory/transfers/<int:transfer_id>/delete", methods=["POST"])
@admin_required
def delete_transfer(transfer_id):
    cid = current_user.company_id if hasattr(current_user, "company_id") and current_user.company_id else 1
    conn = get_connection()
    try:
        conn.execute("BEGIN")
        transfer = conn.execute("SELECT * FROM inventory_transfers WHERE id = ? AND company_id = ?", (transfer_id, cid)).fetchone()
        if not transfer:
            conn.execute("ROLLBACK")
            return jsonify({"ok": False, "error": "Transfer not found"}), 404
            
        items = conn.execute("SELECT product_id, quantity FROM inventory_transfer_items WHERE transfer_id = ? AND company_id = ?", (transfer_id, cid)).fetchall()
        
        source_wid = transfer["source_warehouse_id"]
        dest_wid = transfer["destination_warehouse_id"]
        
        for item in items:
            product_id = item["product_id"]
            qty = float(item["quantity"])
            
            # Revert destination stock (reduce)
            dest_stock_row = conn.execute("SELECT stock_quantity FROM warehouse_inventory WHERE product_id = ? AND warehouse_id = ? AND company_id = ?", (product_id, dest_wid, cid)).fetchone()
            current_dest = float(dest_stock_row["stock_quantity"] or 0) if dest_stock_row else 0.0
            new_dest = current_dest - qty
            if new_dest < 0:
                p_name = conn.execute("SELECT name FROM products WHERE id = ? AND company_id = ?", (product_id, cid)).fetchone()["name"]
                conn.execute("ROLLBACK")
                return jsonify({"ok": False, "error": f"Cannot delete: Reversing this transfer would cause negative stock ({new_dest}) for product {p_name} in destination warehouse."}), 400
            
            conn.execute("UPDATE warehouse_inventory SET stock_quantity = ? WHERE product_id = ? AND warehouse_id = ? AND company_id = ?", (new_dest, product_id, dest_wid, cid))
            
            # Revert source stock (increase)
            source_stock_row = conn.execute("SELECT stock_quantity FROM warehouse_inventory WHERE product_id = ? AND warehouse_id = ? AND company_id = ?", (product_id, source_wid, cid)).fetchone()
            current_source = float(source_stock_row["stock_quantity"] or 0) if source_stock_row else 0.0
            new_source = current_source + qty
            
            conn.execute('''
                INSERT INTO warehouse_inventory (product_id, warehouse_id, stock_quantity, company_id)
                VALUES (?, ?, ?, ?)
                ON CONFLICT(warehouse_id, product_id) DO UPDATE SET stock_quantity = ?
            ''', (product_id, source_wid, new_source, cid, new_source))
            
            # Log reversal
            conn.execute(
                "INSERT INTO inventory_history (product_id, transaction_type, quantity_change, previous_stock, new_stock, reference, warehouse_id, company_id) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                (product_id, "Transfer Reversal", qty, current_source, new_source, f"Reversed Transfer #{transfer_id}", source_wid, cid)
            )
            conn.execute(
                "INSERT INTO inventory_history (product_id, transaction_type, quantity_change, previous_stock, new_stock, reference, warehouse_id, company_id) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                (product_id, "Transfer Reversal", -qty, current_dest, new_dest, f"Reversed Transfer #{transfer_id}", dest_wid, cid)
            )
            
        # Delete records
        conn.execute("DELETE FROM inventory_transfer_items WHERE transfer_id = ? AND company_id = ?", (transfer_id, cid))
        conn.execute("DELETE FROM inventory_transfers WHERE id = ?", (transfer_id,))
        
        conn.commit()
        return jsonify({"ok": True})
    except Exception as e:
        conn.execute("ROLLBACK")
        return jsonify({"ok": False, "error": str(e)}), 500
    finally:
        conn.close()


@app.route("/inventory/delete/<int:product_id>", methods=["POST"])
@admin_required
def inventory_delete(product_id: int):
    cid = current_user.company_id
    is_ajax = request.headers.get("X-Requested-With") == "fetch"

    conn = get_connection()
    ok = False
    error = None
    try:
        # Ensure product belongs to current tenant
        existing = conn.execute("SELECT id FROM products WHERE id = ? AND company_id = ?", (product_id, cid)).fetchone()
        if not existing:
            if is_ajax:
                return jsonify({"ok": False, "error": "Product not found."}), 404
            flash("Product not found.", "error")
            return redirect(url_for("inventory"))

        # Remove references scoped to this company
        conn.execute("UPDATE sale_items SET product_id = NULL WHERE product_id = ? AND company_id = ?", (product_id, cid))
        conn.execute("UPDATE purchase_items SET product_id = NULL WHERE product_id = ? AND company_id = ?", (product_id, cid))
        conn.execute("DELETE FROM inventory_history WHERE product_id = ? AND company_id = ?", (product_id, cid))
        conn.execute("DELETE FROM warehouse_inventory WHERE product_id = ? AND company_id = ?", (product_id, cid))
        
        cur = conn.execute("DELETE FROM products WHERE id = ? AND company_id = ?", (product_id, cid))
        conn.commit()
        ok = cur.rowcount > 0
        if not ok:
            error = "Product not found."
    except Exception as e:
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
    cid = current_user.company_id
    warehouse_id = request.args.get("warehouse_id")
    conn = get_connection()
    try:
        prod = conn.execute("SELECT id FROM products WHERE id = ? AND company_id = ?", (product_id, cid)).fetchone()
        if not prod:
            return jsonify({"ok": False, "error": "Product not found."}), 404

        query = """
            SELECT 
                h.transaction_type, 
                h.quantity_change, 
                h.previous_stock, 
                h.new_stock, 
                h.reference, 
                h.created_at,
                s.name as supplier_name,
                w.name as warehouse_name
            FROM inventory_history h
            LEFT JOIN suppliers s ON (h.supplier_id = s.id AND s.company_id = h.company_id)
            LEFT JOIN warehouses w ON (h.warehouse_id = w.id AND w.company_id = h.company_id)
            WHERE h.product_id = ? AND h.company_id = ?
        """
        params = [product_id, cid]
        
        if warehouse_id:
            query += " AND h.warehouse_id = ?"
            params.append(warehouse_id)
            
        query += " ORDER BY h.created_at DESC"
        
        cur = conn.execute(query, tuple(params))
        history = [dict(row) for row in cur.fetchall()]
        return jsonify({"ok": True, "history": history})
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500
    finally:
        conn.close()


@app.route("/categories/add", methods=["POST"])
@admin_required
def categories_add():
    cid = current_user.company_id
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
        cur = conn.execute("SELECT id, name FROM categories WHERE LOWER(name) = LOWER(?) AND company_id = ?", (name, cid))
        row = cur.fetchone()
        if row:
            category_id = int(row["id"])
        else:
            conn.execute("INSERT INTO categories (company_id, name) VALUES (?, ?)", (cid, name))
            conn.commit()
            cur = conn.execute("SELECT id, name FROM categories WHERE LOWER(name) = LOWER(?) AND company_id = ?", (name, cid))
            row = cur.fetchone()
            category_id = int(row["id"]) if row else None
        return jsonify({"id": category_id, "name": name})
    finally:
        conn.close()


@app.route("/categories", methods=["GET"])
@login_required
def categories_list():
    cid = current_user.company_id
    conn = get_connection()
    try:
        cur = conn.execute("""
            SELECT c.id, c.name, COUNT(p.id) AS product_count 
            FROM categories c 
            LEFT JOIN products p ON (p.category_id = c.id AND p.company_id = c.company_id)
            WHERE c.company_id = ?
            GROUP BY c.id, c.name 
            ORDER BY c.name COLLATE NOCASE
        """, (cid,))
        categories = [dict(row) for row in cur.fetchall()]
    finally:
        conn.close()
    return jsonify(categories)


@app.route("/categories/delete/<int:category_id>", methods=["POST"])
@admin_required
def categories_delete(category_id: int):
    cid = current_user.company_id
    is_ajax = request.headers.get("X-Requested-With") == "fetch"
    conn = get_connection()
    try:
        cat = conn.execute("SELECT id FROM categories WHERE id = ? AND company_id = ?", (category_id, cid)).fetchone()
        if not cat:
            msg = "Category not found."
            return (jsonify({"ok": False, "error": msg}), 404) if is_ajax else redirect(url_for("inventory"))

        cur = conn.execute("SELECT COUNT(*) AS c FROM products WHERE category_id = ? AND company_id = ?", (category_id, cid))
        used_count = int(cur.fetchone()["c"] or 0)
        if used_count > 0:
            msg = "Category cannot be deleted because it is used by one or more products."
            if is_ajax:
                return jsonify({"ok": False, "error": msg}), 409
            return redirect(url_for("inventory"))

        cur2 = conn.execute("DELETE FROM categories WHERE id = ? AND company_id = ?", (category_id, cid))
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
    cid = current_user.company_id
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
        cat = conn.execute("SELECT id FROM categories WHERE id = ? AND company_id = ?", (category_id, cid)).fetchone()
        if not cat:
            if is_ajax:
                return jsonify({"ok": False, "error": "Category not found."}), 404
            return redirect(url_for("inventory"))

        dup = conn.execute("SELECT id FROM categories WHERE LOWER(name) = LOWER(?) AND id != ? AND company_id = ?", (name, category_id, cid)).fetchone()
        if dup:
            if is_ajax:
                return jsonify({"ok": False, "error": "Category name already exists."}), 409
            return redirect(url_for("inventory"))

        cur = conn.execute(
            "UPDATE categories SET name = ? WHERE id = ? AND company_id = ?",
            (name, category_id, cid),
        )
        conn.commit()
        if cur.rowcount == 0:
            if is_ajax:
                return jsonify({"ok": False, "error": "Category not found."}), 404
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
    Returns all brands for current tenant as JSON [{id, name}].
    If brands table is empty for tenant, derive initial values from products.brand.
    """
    cid = current_user.company_id
    conn = get_connection()
    try:
        # Backfill brands from existing products for current company (idempotent).
        conn.execute(
            """
            INSERT OR IGNORE INTO brands (company_id, name)
            SELECT DISTINCT ?, TRIM(brand)
            FROM products
            WHERE company_id = ? AND brand IS NOT NULL AND TRIM(brand) != ''
            """,
            (cid, cid),
        )
        conn.commit()

        cur = conn.execute(
            "SELECT id, name FROM brands WHERE company_id = ? ORDER BY name COLLATE NOCASE",
            (cid,),
        )
        return jsonify([{"id": int(r["id"]), "name": r["name"]} for r in cur.fetchall()])
    finally:
        conn.close()


@app.route("/brands/add", methods=["POST"])
@admin_required
def brands_add():
    cid = current_user.company_id
    is_json = request.is_json
    data = request.get_json(silent=True) if is_json else {}
    if not data:
        data = request.form or {}

    name = (data.get("name") or "").strip()
    if not name:
        if is_json:
            return jsonify({"ok": False, "error": "Brand name is required."}), 400
        else:
            return "Brand name is required.", 400

    show_on_website = data.get("show_on_website")
    if show_on_website is None:
        show_on_website = False if not is_json and request.form else True
    elif isinstance(show_on_website, str):
        show_on_website = show_on_website.lower() in ("true", "1", "on")
    else:
        show_on_website = bool(show_on_website)

    commission_rate = float(data.get("commission_rate") or 0)

    # Handle file upload
    logo = request.files.get("logo")
    if logo and logo.filename:
        import os
        brands_dir = os.path.join(app.root_path, "static", "logos", "brands")
        os.makedirs(brands_dir, exist_ok=True)
        logo.save(os.path.join(brands_dir, f"{name}.png"))

    conn = get_connection()
    try:
        cur = conn.execute("SELECT id, name FROM brands WHERE LOWER(name) = LOWER(?) AND company_id = ?", (name, cid))
        row = cur.fetchone()
        if not row:
            conn.execute(
                "INSERT INTO brands (company_id, name, commission_rate, show_on_website) VALUES (?, ?, ?, ?)",
                (cid, name, commission_rate, bool(show_on_website)),
            )
            conn.commit()
            cur = conn.execute("SELECT id, name FROM brands WHERE LOWER(name) = LOWER(?) AND company_id = ?", (name, cid))
            row = cur.fetchone()

        if row is None:
            if is_json:
                return jsonify({"ok": False, "error": "Failed to create brand."}), 500
            else:
                return "Failed to create brand.", 500

        if is_json:
            return jsonify({"ok": True, "id": int(row["id"]), "name": row["name"]})
        else:
            return redirect(url_for("suppliers_page"))
    finally:
        conn.close()



@app.route("/suppliers", methods=["GET"])
@admin_required
def suppliers_page():
    cid = current_user.company_id if hasattr(current_user, "company_id") and current_user.company_id else 1
    conn = get_connection()
    try:
        cur_suppliers = conn.execute("""
            SELECT s.*, COUNT(p.id) as products_count,
                   (SELECT COALESCE(SUM(remaining_amount), 0) FROM purchases WHERE supplier_id = s.id AND company_id = ?) as total_balance,
                   (SELECT COALESCE(SUM(amount_paid), 0) FROM purchases WHERE supplier_id = s.id AND company_id = ?) as total_paid
            FROM suppliers s
            LEFT JOIN products p ON s.id = p.supplier_id AND p.company_id = ?
            WHERE s.company_id = ?
            GROUP BY s.id
            ORDER BY s.name ASC
        """, (cid, cid, cid, cid))
        suppliers = [dict(r) for r in cur_suppliers.fetchall()]
        
        cur_brands = conn.execute("""
            SELECT b.*, b.commission_rate, COUNT(p.id) as products_count
            FROM brands b
            LEFT JOIN products p ON b.name = p.brand AND p.company_id = ?
            WHERE b.company_id = ?
            GROUP BY b.id
            ORDER BY b.name ASC
        """, (cid, cid))
        brands = [dict(r) for r in cur_brands.fetchall()]
        
        return render_template("suppliers.html", suppliers=suppliers, brands=brands)
    finally:
        conn.close()

@app.route("/suppliers/add", methods=["POST"])
@admin_required
def suppliers_add():
    cid = current_user.company_id if hasattr(current_user, "company_id") and current_user.company_id else 1
    name = request.form.get("name", "").strip()
    contact_name = request.form.get("contact_name", "").strip()
    phone = request.form.get("phone", "").strip()
    address = request.form.get("address", "").strip()
    
    if not name:
        return "Supplier Business Name is required.", 400
        
    conn = get_connection()
    try:
        conn.execute("INSERT INTO suppliers (name, contact_name, phone, address, company_id) VALUES (?, ?, ?, ?, ?)", (name, contact_name, phone, address, cid))
        conn.commit()
    finally:
        conn.close()
    return redirect(url_for("suppliers_page"))

@app.route("/suppliers/edit/<int:supplier_id>", methods=["POST"])
@admin_required
def suppliers_edit(supplier_id):
    cid = current_user.company_id if hasattr(current_user, "company_id") and current_user.company_id else 1
    name = request.form.get("name", "").strip()
    contact_name = request.form.get("contact_name", "").strip()
    phone = request.form.get("phone", "").strip()
    address = request.form.get("address", "").strip()
    
    if not name:
        return "Supplier Business Name is required.", 400
        
    conn = get_connection()
    try:
        cur = conn.execute("SELECT id FROM suppliers WHERE id = ? AND company_id = ?", (supplier_id, cid)).fetchone()
        if not cur:
            abort(404)
        conn.execute("UPDATE suppliers SET name = ?, contact_name = ?, phone = ?, address = ? WHERE id = ? AND company_id = ?", (name, contact_name, phone, address, supplier_id, cid))
        conn.commit()
    finally:
        conn.close()
    return redirect(url_for("suppliers_page"))

@app.route("/suppliers/delete/<int:supplier_id>", methods=["POST"])
@admin_required
def suppliers_delete(supplier_id):
    cid = current_user.company_id if hasattr(current_user, "company_id") and current_user.company_id else 1
    conn = get_connection()
    try:
        cur = conn.execute("SELECT id FROM suppliers WHERE id = ? AND company_id = ?", (supplier_id, cid)).fetchone()
        if not cur:
            abort(404)
        conn.execute("DELETE FROM suppliers WHERE id = ? AND company_id = ?", (supplier_id, cid))
        conn.execute("UPDATE products SET supplier_id = NULL WHERE supplier_id = ? AND company_id = ?", (supplier_id, cid))
        conn.execute("UPDATE inventory_history SET supplier_id = NULL WHERE supplier_id = ? AND company_id = ?", (supplier_id, cid))
        conn.commit()
    finally:
        conn.close()
    return redirect(url_for("suppliers_page"))

@app.route("/suppliers/<int:supplier_id>/history", methods=["GET"])
@admin_required
def supplier_history(supplier_id):
    cid = current_user.company_id if hasattr(current_user, "company_id") and current_user.company_id else 1
    conn = get_connection()
    try:
        cur = conn.execute("SELECT id FROM suppliers WHERE id = ? AND company_id = ?", (supplier_id, cid)).fetchone()
        if not cur:
            abort(404)
        rows = conn.execute(
            '''
            SELECT
                date(ih.created_at) as addition_date,
                p.name AS product_name,
                COALESCE(SUM(ih.quantity_change), 0) AS total_added,
                COALESCE(SUM(ih.quantity_change * p.cost_price), 0) AS total_value
            FROM inventory_history ih
            JOIN products p ON p.id = ih.product_id AND p.company_id = ?
            WHERE p.supplier_id = ? AND ih.company_id = ? AND ih.transaction_type = 'IN'
              AND ih.reference IN ('Initial Stock', 'Initial Stock (Legacy)', 'Manual Edit', 'Manual Edit (Edit Product)')
            GROUP BY date(ih.created_at), p.id
            ORDER BY addition_date DESC, p.name ASC
            ''', (cid, supplier_id, cid)
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
    cid = current_user.company_id
    name = request.form.get("name", "").strip()
    commission_rate = float(request.form.get("commission_rate") or 0)
    
    show_on_website = request.form.get("show_on_website")
    show_on_website = True if show_on_website == "on" else False

    if not name:
        return "Brand name is required.", 400

    logo = request.files.get("logo")
    if logo and logo.filename:
        import os
        brands_dir = os.path.join(app.root_path, "static", "logos", "brands")
        os.makedirs(brands_dir, exist_ok=True)
        logo.save(os.path.join(brands_dir, f"{name}.png"))
        
    conn = get_connection()
    try:
        old_brand_name = conn.execute("SELECT name FROM brands WHERE id = ? AND company_id = ?", (brand_id, cid)).fetchone()
        if old_brand_name:
            old_name = old_brand_name["name"]
            
            if old_name != name:
                import os
                brands_dir = os.path.join(app.root_path, "static", "logos", "brands")
                old_logo_path = os.path.join(brands_dir, f"{old_name}.png")
                new_logo_path = os.path.join(brands_dir, f"{name}.png")
                if os.path.exists(old_logo_path) and not (logo and logo.filename):
                    os.rename(old_logo_path, new_logo_path)

            conn.execute("UPDATE brands SET name = ?, commission_rate = ?, show_on_website = ? WHERE id = ? AND company_id = ?", (name, commission_rate, bool(show_on_website), brand_id, cid))
            conn.execute("UPDATE products SET brand = ? WHERE brand = ? AND company_id = ?", (name, old_name, cid))
            conn.commit()
    finally:
        conn.close()
    return redirect(url_for("suppliers_page"))

@app.route("/brands/delete/<int:brand_id>", methods=["POST"])
@admin_required
def brands_delete(brand_id):
    cid = current_user.company_id
    conn = get_connection()
    try:
        old_brand_name = conn.execute("SELECT name FROM brands WHERE id = ? AND company_id = ?", (brand_id, cid)).fetchone()
        if old_brand_name:
            old_name = old_brand_name["name"]
            conn.execute("DELETE FROM brands WHERE id = ? AND company_id = ?", (brand_id, cid))
            conn.execute("UPDATE products SET brand = NULL WHERE brand = ? AND company_id = ?", (old_name, cid))
            conn.commit()
    finally:
        conn.close()
    return redirect(url_for("suppliers_page"))

@app.route("/products/list", methods=["GET"])
@login_required
def products_list():
    cid = current_user.company_id
    is_admin = current_user.role in ('admin', 'superadmin')
    warehouse_id = request.args.get("warehouse_id")
    wid = int(warehouse_id) if warehouse_id else (current_user.warehouse_id or 1)
    conn = get_connection()
    try:
        query = """
            SELECT
                p.id AS id,
                p.name AS name,
                MAX(b.id) AS brand_id,
                p.brand AS brand_name,
                p.category_id AS category_id,
                p.unit AS unit,
                p.cost_price AS cost_price,
                p.selling_price AS selling_price,
                COALESCE((SELECT stock_quantity FROM warehouse_inventory WHERE product_id = p.id AND warehouse_id = ? AND company_id = ?), 0) AS stock_quantity,
                p.image_url AS image_url,
                p.is_open AS is_open
            FROM products p
            LEFT JOIN brands b
                ON (LOWER(b.name) = LOWER(p.brand) AND (b.company_id = p.company_id OR b.company_id IS NULL))
            WHERE p.company_id = ?
        """
        params = [wid, cid, cid]
        if current_user.role != 'admin':
            query += " AND EXISTS (SELECT 1 FROM warehouse_inventory wi WHERE wi.product_id = p.id AND wi.warehouse_id = ? AND wi.company_id = ?)"
            params.extend([wid, cid])
            
        query += """
            GROUP BY p.id
            ORDER BY p.id DESC
        """
        cur = conn.execute(query, tuple(params))
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
                    "cost_price": float(r["cost_price"] or 0) if is_admin else None,
                    "selling_price": float(r["selling_price"] or 0),
                    "stock_quantity": round(float(r["stock_quantity"] or 0), 4),
                    "image_url": r["image_url"],
                    "is_open": int(r["is_open"] or 0),
                }
                for r in rows
            ]
        )
    finally:
        conn.close()


@app.route("/brands/search", methods=["GET"])
@login_required
def brands_search():
    cid = current_user.company_id
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
            WHERE company_id = ? AND brand IS NOT NULL AND TRIM(brand) != '' AND brand LIKE ?
            ORDER BY brand COLLATE NOCASE
            LIMIT 15
            """,
            (cid, like),
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
        tables = ["users", "customers", "categories", "brands", "products", "product_variants", "sales", "sale_items", "warehouses", "warehouse_inventory", "inventory_history", "suppliers", "purchases", "purchase_items", "expenses", "supplier_payments"]
        
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
    cid = current_user.company_id
    conn = get_connection()
    try:
        cur = conn.execute(
            """
            SELECT
                c.id,
                c.name,
                c.bill_address,
                c.ship_address,
                c.area,
                c.state,
                c.phone,
                c.email,
                c.terms,
                c.salesman_id,
                u.username AS salesman_name,
                c.created_at,
                COUNT(s.id) as invoices_count,
                COALESCE(SUM(s.grand_total), 0) as total_invoiced,
                COALESCE(SUM(s.amount_paid), 0) as total_paid,
                COALESCE(SUM(s.remaining_amount), 0) as total_receivable
            FROM customers c
            LEFT JOIN users u ON c.salesman_id = u.id
            LEFT JOIN sales s ON c.id = s.customer_id AND s.status != 'quote' AND s.company_id = c.company_id
            WHERE c.company_id = ?
            GROUP BY c.id, u.username
            ORDER BY c.created_at DESC, c.id DESC
            """,
            (cid,)
        )
        customers_list = [dict(row) for row in cur.fetchall()]

        cur = conn.execute("SELECT COUNT(*) AS c FROM customers WHERE company_id = ?", (cid,))
        total_customers = int(cur.fetchone()["c"] or 0)

        cur = conn.execute(
            """
            SELECT COUNT(DISTINCT NULLIF(TRIM(area), '')) AS c
            FROM customers
            WHERE company_id = ?
            """,
            (cid,)
        )
        areas_covered = int(cur.fetchone()["c"] or 0)
        cur = conn.execute("SELECT id, username FROM users WHERE company_id = ? AND is_active = 1 ORDER BY username", (cid,))
        users_list = [dict(row) for row in cur.fetchall()]
    finally:
        conn.close()

    error = request.args.get("error")
    return render_template(
        "customers.html",
        customers=customers_list,
        users=users_list,
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

    salesman_id_raw = (request.form.get("salesman_id") or "").strip()
    warehouse_id_raw = (request.form.get("warehouse_id") or "").strip()
    salesman_id = int(salesman_id_raw) if salesman_id_raw else None

    cid = current_user.company_id
    conn = get_connection()
    try:
        conn.execute(
            """
            INSERT INTO customers
                (company_id, name, bill_address, ship_address, area, state, phone, email, terms, salesman_id)
            VALUES
                (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (cid, full_name, bill_address or None, ship_address or None, area, state, phone, email, terms, salesman_id),
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

    salesman_id_raw = (request.form.get("salesman_id") or "").strip()
    warehouse_id_raw = (request.form.get("warehouse_id") or "").strip()
    salesman_id = int(salesman_id_raw) if salesman_id_raw else None

    cid = current_user.company_id
    conn = get_connection()
    try:
        cur = conn.execute("SELECT id FROM customers WHERE id = ? AND company_id = ?", (customer_id, cid)).fetchone()
        if not cur:
            abort(404)
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
                terms = ?,
                salesman_id = ?
            WHERE id = ? AND company_id = ?
            """,
            (full_name, bill_address or None, ship_address or None, area, state, phone, email, terms, salesman_id, customer_id, cid),
        )
        conn.commit()
    finally:
        conn.close()

    return redirect(url_for("customers"))


@app.route("/customers/delete/<int:customer_id>", methods=["POST"])
@admin_required
def customers_delete(customer_id: int):
    cid = current_user.company_id
    conn = get_connection()
    try:
        cur = conn.execute("SELECT id FROM customers WHERE id = ? AND company_id = ?", (customer_id, cid)).fetchone()
        if not cur:
            abort(404)
        # Keep sales history rows, but detach them from the deleted customer.
        conn.execute("UPDATE sales SET customer_id = NULL WHERE customer_id = ? AND company_id = ?", (customer_id, cid))
        conn.execute("DELETE FROM customers WHERE id = ? AND company_id = ?", (customer_id, cid))
        conn.commit()
    finally:
        conn.close()

    return redirect(url_for("customers"))

@app.route("/customers/list", methods=["GET"])
@login_required
def customers_list():
    cid = current_user.company_id
    conn = get_connection()
    try:
        if current_user.role in ('admin', 'superadmin'):
            cur = conn.execute("SELECT * FROM customers WHERE company_id = ? ORDER BY name", (cid,))
        else:
            cur = conn.execute("SELECT * FROM customers WHERE company_id = ? AND salesman_id = ? ORDER BY name", (cid, current_user.id))
        cust_list = [dict(r) for r in cur.fetchall()]
        return jsonify(cust_list)
    finally:
        conn.close()


@app.route("/customers/<int:customer_id>/history", methods=["GET"])
@admin_required
def customers_history(customer_id: int):
    cid = current_user.company_id
    conn = get_connection()
    try:
        cust = conn.execute("SELECT id FROM customers WHERE id = ? AND company_id = ?", (customer_id, cid)).fetchone()
        if not cust:
            return jsonify([])
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
            LEFT JOIN sale_items si ON si.sale_id = s.id AND si.company_id = s.company_id
            WHERE s.customer_id = ? AND s.company_id = ?
            GROUP BY s.id
            ORDER BY s.invoice_date DESC
            """,
            (customer_id, cid),
        )
        rows = cur.fetchall()
        return jsonify([dict(r) for r in rows])
    finally:
        conn.close()


@app.route("/sales")
@admin_required
def sales():
    cid = current_user.company_id
    conn = get_connection()
    try:
        if current_user.role in ('admin', 'superadmin'):
            customers = conn.execute(
                """
                SELECT id, name, terms
                FROM customers
                WHERE company_id = ?
                ORDER BY name COLLATE NOCASE
                """,
                (cid,)
            ).fetchall()
        else:
            customers = conn.execute(
                """
                SELECT id, name, terms
                FROM customers
                WHERE company_id = ? AND salesman_id = ?
                ORDER BY name COLLATE NOCASE
                """,
                (cid, current_user.id)
            ).fetchall()
        customers_list = [dict(r) for r in customers]
        users_rows = conn.execute("SELECT id, username, role FROM users WHERE company_id = ? AND is_active = 1 ORDER BY username", (cid,)).fetchall()
        users_list = [dict(r) for r in users_rows]
        
        products_rows = conn.execute("SELECT id, name FROM products WHERE company_id = ? ORDER BY name COLLATE NOCASE", (cid,)).fetchall()
        products_list = [dict(r) for r in products_rows]

        query = """
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
                COALESCE(SUM((si.qty * COALESCE(si.packing_multiplier, 1.0) * si.cost_price) + COALESCE(si.commission_amount, 0)), 0) AS total_cost,
                u.username AS salesman_name
            FROM sales s
            LEFT JOIN customers c ON c.id = s.customer_id
            LEFT JOIN sale_items si ON si.sale_id = s.id AND si.company_id = s.company_id
            LEFT JOIN users u ON u.id = s.salesman_id
            WHERE s.company_id = ? {salesman_extra}
            GROUP BY s.id, c.name, u.username
            ORDER BY s.invoice_date DESC, s.id DESC
            LIMIT 10
            """
        is_admin = current_user.role in ('admin', 'superadmin')
        if not is_admin:
            recent_sales_rows = conn.execute(query.format(salesman_extra="AND s.salesman_id = ?"), (cid, current_user.id)).fetchall()
        else:
            recent_sales_rows = conn.execute(query.format(salesman_extra=""), (cid,)).fetchall()
        recent_sales = []
        for r in recent_sales_rows:
            d = dict(r)
            rev = float(d["grand_total"] or 0)
            cost = float(d["total_cost"] or 0)
            if is_admin:
                d["profit_margin"] = round(((rev - cost) / rev * 100), 2) if rev > 0 else 0
                d["profit_amount"] = round(rev - cost, 2)
            else:
                d["total_cost"] = None
                d["profit_margin"] = None
                d["profit_amount"] = None
            recent_sales.append(d)
        warehouses_rows = conn.execute("SELECT id, name FROM warehouses WHERE company_id = ? ORDER BY name", (cid,)).fetchall()
        warehouses_list = [dict(r) for r in warehouses_rows]
    finally:
        conn.close()

    return render_template(
        "sales.html",
        customers=customers_list,
        recent_sales=recent_sales,
        next_invoice_number=get_next_invoice_number(cid),
        today=date.today().isoformat(),
        all_users=users_list,
        warehouses=warehouses_list,
        products=products_list
    )
@app.route("/sales/next-invoice", methods=["GET"])
@login_required
def sales_next_invoice():
    return jsonify({"invoice_number": get_next_invoice_number(current_user.company_id)})


@app.route("/products/search", methods=["GET"])
@login_required
def products_search():
    cid = current_user.company_id
    is_admin = current_user.role in ('admin', 'superadmin')
    q = (request.args.get("q") or "").strip()
    like = f"%{q}%"
    warehouse_id = request.args.get("warehouse_id")
    if current_user.role != 'admin' and current_user.warehouse_id:
        warehouse_id = current_user.warehouse_id
    wid = int(warehouse_id) if warehouse_id else (current_user.warehouse_id or 1)
        
    stock_query = "COALESCE((SELECT stock_quantity FROM warehouse_inventory WHERE product_id = products.id AND warehouse_id = ? AND company_id = ?), 0)"
    
    conn = get_connection()
    try:
        base_query = f"""
            SELECT
                id,
                name,
                brand,
                selling_price,
                cost_price,
                unit,
                {stock_query} AS stock_quantity,
                is_open,
                supplier_id
            FROM products
            WHERE company_id = ?
        """
        params = [wid, cid, cid]
        
        if q:
            base_query += " AND (name LIKE ? OR brand LIKE ?)"
            params.extend([like, like])
            
        if current_user.role != 'admin':
            base_query += " AND EXISTS (SELECT 1 FROM warehouse_inventory wi WHERE wi.product_id = products.id AND wi.warehouse_id = ? AND wi.company_id = ?)"
            params.extend([wid, cid])
            
        if not q:
            base_query += " ORDER BY name COLLATE NOCASE LIMIT 20"
        else:
            base_query += " ORDER BY name COLLATE NOCASE LIMIT 15"
            
        cur = conn.execute(base_query, tuple(params))
        results = []
        for r in cur.fetchall():
            results.append(
                {
                    "id": r["id"],
                    "name": r["name"],
                    "brand": r["brand"],
                    "selling_price": r["selling_price"],
                    "cost_price": r["cost_price"] if is_admin else None,
                    "unit": r["unit"],
                    "stock_quantity": r["stock_quantity"],
                    "is_open": r["is_open"],
                    "supplier_id": r["supplier_id"],
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
    warehouse_id = (request.args.get("warehouse_id") or "").strip()
    product_id = (request.args.get("product_id") or "").strip()
    search = (request.args.get("search") or "").strip()

    cid = current_user.company_id
    conditions = ["s.company_id = ?"]
    params = [cid]

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
            
    if product_id and product_id not in ("all", ""):
        try:
            product_id_int = int(product_id)
            conditions.append("s.id IN (SELECT sale_id FROM sale_items WHERE product_id = ? AND company_id = ?)")
            params.extend([product_id_int, cid])
        except ValueError:
            pass
            
    if current_user.role not in ('admin', 'superadmin'):
        conditions.append("s.salesman_id = ?")
        params.append(current_user.id)
    else:
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
        
    if warehouse_id and warehouse_id not in ("all", ""):
        try:
            warehouse_id_int = int(warehouse_id)
            conditions.append("s.warehouse_id = ?")
            params.append(warehouse_id_int)
        except ValueError:
            pass

    if search:
        search_term = f"%{search.lower()}%"
        conditions.append("(LOWER(s.invoice_number) LIKE ? OR LOWER(c.name) LIKE ?)")
        params.extend([search_term, search_term])

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
                s.commission_amount,
                c.name as customer_name,
                c.terms as customer_terms,
                u.username as salesman_name,
                (SELECT COALESCE(SUM((si.qty * COALESCE(si.packing_multiplier, 1.0) * si.cost_price) + COALESCE(si.commission_amount, 0)), 0) FROM sale_items si WHERE si.sale_id = s.id AND si.company_id = s.company_id) as total_cost
            FROM sales s
            LEFT JOIN customers c ON c.id = s.customer_id
            LEFT JOIN users u ON u.id = s.salesman_id
            {where_sql}
            ORDER BY s.id DESC
            """
        , params)
        sales_list = []
        is_admin = current_user.role in ('admin', 'superadmin')
        for r in cur.fetchall():
            d = dict(r)
            rev = float(d["grand_total"] or 0)
            cost = float(d["total_cost"] or 0)
            if is_admin:
                profit = rev - cost
                d["profit_margin"] = round((profit / rev * 100), 2) if rev > 0 else 0
                d["profit_amount"] = round(profit, 2)
            else:
                d["total_cost"] = None
                d["profit_margin"] = None
                d["profit_amount"] = None
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
    warehouse_id = (request.args.get("warehouse_id") or "").strip()

    cid = current_user.company_id
    conditions = ["s.company_id = ?"]
    params = [cid]

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
        
    if warehouse_id and warehouse_id not in ("all", ""):
        try:
            warehouse_id_int = int(warehouse_id)
            conditions.append("s.warehouse_id = ?")
            params.append(warehouse_id_int)
        except ValueError:
            pass
    if search:
        search_term = f"%{search.lower()}%"
        conditions.append("(LOWER(s.invoice_number) LIKE ? OR LOWER(c.name) LIKE ?)")
        params.extend([search_term, search_term])

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
                s.commission_amount,
                c.name as customer_name,
                (SELECT COUNT(si.id) FROM sale_items si WHERE si.sale_id = s.id AND si.company_id = s.company_id) as item_count,
                (SELECT COALESCE(SUM((si.qty * COALESCE(si.packing_multiplier, 1.0) * si.cost_price) + COALESCE(si.commission_amount, 0)), 0) FROM sale_items si WHERE si.sale_id = s.id AND si.company_id = s.company_id) as total_cost
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
        commission = float(d["commission_amount"] or 0)
        profit = rev - cost
        margin = round((profit / rev * 100), 2) if rev > 0 else 0.0
        profit_amount = round(profit, 2)
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


import csv
from io import StringIO
from flask import Response

@app.route("/sales/import-csv-template", methods=["GET"])
@admin_required
def sales_import_csv_template():
    output = StringIO()
    writer = csv.writer(output)
    writer.writerow(["Invoice Number", "Invoice Date", "Customer Name", "Product Name", "Quantity", "Rate", "Warehouse Name", "Salesman Name"])
    writer.writerow(["INV-OLD-001", "2026-09-01", "Walk-in Customer", "Chicken Flavor Spread Classic", 10, 5.0, "Main Warehouse", "salesman"])
    writer.writerow(["INV-OLD-001", "2026-09-01", "Walk-in Customer", "Chicken Flavor Spread BBQ", 5, 5.5, "Main Warehouse", "salesman"])
    writer.writerow(["INV-OLD-002", "2026-09-02", "Walk-in Customer", "ZAIN FOOD-BLACK PEPPER (200G-7 OZ)", 20, 3.0, "LA Warehouse", "salesman"])
    output.seek(0)
    return Response(
        output.getvalue(),
        mimetype="text/csv",
        headers={"Content-Disposition": "attachment;filename=sales_import_template.csv"}
    )

@app.route("/sales/import-csv", methods=["POST"])
@admin_required
def sales_import_csv():
    if 'file' not in request.files:
        return jsonify({"success": False, "error": "No file uploaded."})
    
    file = request.files['file']
    if file.filename == '':
        return jsonify({"success": False, "error": "No file selected."})
    
    if not file.filename.endswith('.csv'):
        return jsonify({"success": False, "error": "Invalid file type. Please upload a CSV file."})
    
    try:
        content = file.read().decode('utf-8-sig')
        reader = csv.DictReader(StringIO(content))
        
        # Validate headers
        required_headers = [
            "Invoice Number", "Invoice Date", "Customer Name", 
            "Product Name", "Quantity", "Rate", "Warehouse Name",
            "Salesman Name"
        ]
        
        headers = reader.fieldnames
        if not headers or not all(h in headers for h in required_headers):
            return jsonify({"success": False, "error": f"Invalid CSV headers. Expected: {', '.join(required_headers)}"})
        
        rows = list(reader)
        if not rows:
            return jsonify({"success": False, "error": "The CSV file is empty."})
        
        conn = get_connection()
        try:
            # 1. Validation Pass
            customers_cache = {}
            products_cache = {}
            warehouses_cache = {}
            users_cache = {}
            
            invoices = {} # Group by Invoice Number
            
            for i, row in enumerate(rows, start=2): # +2 for 1-based index and header row
                inv_num = row.get("Invoice Number", "").strip()
                inv_date = row.get("Invoice Date", "").strip()
                c_name = row.get("Customer Name", "").strip()
                p_name = row.get("Product Name", "").strip()
                qty_str = row.get("Quantity", "").strip()
                rate_str = row.get("Rate", "").strip()
                w_name = row.get("Warehouse Name", "").strip()
                s_name = row.get("Salesman Name", "").strip()
                
                if not inv_num or not inv_date or not c_name or not p_name or not qty_str or not rate_str or not w_name or not s_name:
                    return jsonify({"success": False, "error": f"Row {i}: Missing required fields."})
                
                try:
                    qty = float(qty_str)
                    rate = float(rate_str)
                except ValueError:
                    return jsonify({"success": False, "error": f"Row {i}: Quantity and Rate must be numbers."})
                
                cid = current_user.company_id

                # Validate Customer
                if c_name not in customers_cache:
                    c_row = conn.execute("SELECT id FROM customers WHERE name = ? AND company_id = ?", (c_name, cid)).fetchone()
                    if not c_row:
                        return jsonify({"success": False, "error": f"Row {i}: Customer '{c_name}' not found in database."})
                    customers_cache[c_name] = c_row["id"]
                    
                # Validate Product
                if p_name not in products_cache:
                    p_row = conn.execute("SELECT id, cost_price FROM products WHERE name = ? AND company_id = ?", (p_name, cid)).fetchone()
                    if not p_row:
                        return jsonify({"success": False, "error": f"Row {i}: Product '{p_name}' not found in database."})
                    products_cache[p_name] = p_row
                    
                # Validate Warehouse
                if w_name not in warehouses_cache:
                    w_row = conn.execute("SELECT id, commission_applies FROM warehouses WHERE name = ? AND company_id = ?", (w_name, cid)).fetchone()
                    if not w_row:
                        return jsonify({"success": False, "error": f"Row {i}: Warehouse '{w_name}' not found in database."})
                    warehouses_cache[w_name] = w_row
                    
                # Validate Salesman
                if s_name not in users_cache:
                    u_row = conn.execute("SELECT id FROM users WHERE username = ? AND company_id = ?", (s_name, cid)).fetchone()
                    if not u_row:
                        return jsonify({"success": False, "error": f"Row {i}: Salesman '{s_name}' not found in database (username)."})
                    users_cache[s_name] = u_row["id"]
                
                # Group items by CSV Invoice Number (used to club multiple items into a single invoice)
                if inv_num not in invoices:
                    invoices[inv_num] = {
                        "date": inv_date,
                        "customer_id": customers_cache[c_name],
                        "warehouse_id": warehouses_cache[w_name]["id"],
                        "commission_applies": warehouses_cache[w_name]["commission_applies"],
                        "salesman_id": users_cache[s_name],
                        "items": []
                    }
                else:
                    # Enforce that all rows for the same invoice have the same customer, date, warehouse, salesman
                    if invoices[inv_num]["customer_id"] != customers_cache[c_name]:
                        return jsonify({"success": False, "error": f"Row {i}: Invoice '{inv_num}' has multiple different customers."})
                    if invoices[inv_num]["warehouse_id"] != warehouses_cache[w_name]["id"]:
                        return jsonify({"success": False, "error": f"Row {i}: Invoice '{inv_num}' has multiple different warehouses."})
                    if invoices[inv_num]["salesman_id"] != users_cache[s_name]:
                        return jsonify({"success": False, "error": f"Row {i}: Invoice '{inv_num}' has multiple different salesmen."})
                
                # Pre-calculate item commission if applies
                comm_amount = 0.0
                if invoices[inv_num]["commission_applies"]:
                    br_row = conn.execute("SELECT b.commission_rate FROM products p LEFT JOIN brands b ON LOWER(p.brand) = LOWER(b.name) AND (b.company_id = p.company_id OR b.company_id IS NULL) WHERE p.id = ? AND p.company_id = ?", (products_cache[p_name]["id"], cid)).fetchone()
                    item_comm_rate = float(br_row["commission_rate"] or 0) if br_row and br_row["commission_rate"] is not None else 0
                    comm_amount = round((qty * rate) * (item_comm_rate / 100), 2)
                    
                invoices[inv_num]["items"].append({
                    "product_id": products_cache[p_name]["id"],
                    "cost_price": float(products_cache[p_name]["cost_price"] or 0),
                    "packing_multiplier": 1.0,
                    "qty": qty,
                    "rate": rate,
                    "amount": qty * rate,
                    "commission_amount": comm_amount
                })

            # 2. Insertion Pass: Auto-generate sequential invoice numbers continuing after last sale for this company
            cid = current_user.company_id
            comp = get_company(cid) or {}
            prefix = comp.get("invoice_prefix") or "INV-"
            starting_num = int(comp.get("starting_invoice_number") or 1)

            rows = conn.execute(
                "SELECT invoice_number FROM sales WHERE company_id = ?", (cid,)
            ).fetchall()
            nums = []
            for r in rows:
                inv = str(r["invoice_number"]).strip()
                m = re.search(r"(\d+)$", inv)
                if m:
                    nums.append(int(m.group(1)))
            next_num = max(max(nums) + 1, starting_num) if nums else starting_num

            generated_invoices = []
            for club_key, data in invoices.items():
                auto_inv_number = f"{prefix}{next_num:06d}"
                next_num += 1
                generated_invoices.append(auto_inv_number)

                subtotal = sum(item["amount"] for item in data["items"])
                total_comm = sum(item["commission_amount"] for item in data["items"])
                
                # Note: Defaulting payment to cash and fully paid for old invoices
                sale_cur = conn.execute(
                    '''INSERT INTO sales 
                       (company_id, invoice_number, customer_id, invoice_date, payment_type, subtotal, grand_total, amount_paid, remaining_amount, status, warehouse_id, salesman_id, commission_amount, commission_rate, notes) 
                       VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)''',
                    (cid, auto_inv_number, data["customer_id"], data["date"], 'cash', subtotal, subtotal, subtotal, 0, 'paid', data["warehouse_id"], data["salesman_id"], total_comm, 0, f"Bulk import (Old ref: {club_key})")
                )
                sale_id = sale_cur.lastrowid
                
                for item in data["items"]:
                    conn.execute(
                        '''INSERT INTO sale_items 
                           (company_id, sale_id, product_id, qty, rate, amount, cost_price, packing_multiplier, commission_amount) 
                           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)''',
                        (cid, sale_id, item["product_id"], item["qty"], item["rate"], item["amount"], item["cost_price"], item["packing_multiplier"], item["commission_amount"])
                    )
                    
                    # Fetch old stock for inventory tracking
                    wh_stock_row = conn.execute(
                        "SELECT stock_quantity FROM warehouse_inventory WHERE warehouse_id = ? AND product_id = ? AND company_id = ?",
                        (data["warehouse_id"], item["product_id"], cid)
                    ).fetchone()
                    old_stock = wh_stock_row["stock_quantity"] if wh_stock_row and wh_stock_row["stock_quantity"] is not None else 0
                    new_stock = old_stock - item["qty"]

                    # Adjust stock in warehouse_inventory
                    conn.execute(
                        '''UPDATE warehouse_inventory 
                           SET stock_quantity = stock_quantity - ? 
                           WHERE warehouse_id = ? AND product_id = ? AND company_id = ?''',
                        (item["qty"], data["warehouse_id"], item["product_id"], cid)
                    )
                    # Adjust global stock in products table
                    conn.execute(
                        "UPDATE products SET stock_quantity = stock_quantity - ? WHERE id = ? AND company_id = ?",
                        (item["qty"], item["product_id"], cid)
                    )
                    # Add to inventory history
                    conn.execute('''
                        INSERT INTO inventory_history (company_id, product_id, transaction_type, quantity_change, previous_stock, new_stock, reference, warehouse_id)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                    ''', (cid, item["product_id"], 'OUT', -item["qty"], old_stock, new_stock, f'Invoice #{auto_inv_number}', data["warehouse_id"]))
            
            conn.commit()
            if generated_invoices:
                if len(generated_invoices) == 1:
                    inv_range_str = generated_invoices[0]
                else:
                    inv_range_str = f"{generated_invoices[0]} to {generated_invoices[-1]}"
                msg = f"Successfully imported {len(invoices)} invoice(s) ({inv_range_str})."
            else:
                msg = "No invoices found to import."
            return jsonify({"success": True, "message": msg})
        except Exception as e:
            conn.rollback()
            return jsonify({"success": False, "error": f"Database error: {str(e)}"})
        finally:
            conn.close()
    except Exception as e:
        return jsonify({"success": False, "error": f"Error parsing CSV: {str(e)}"})

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
    warehouse_id_raw = (request.form.get("warehouse_id") or "").strip()
    discount_amount_raw = (request.form.get("discount_amount") or "").strip()
    items_json = request.form.get("items_json") or "[]"
    generate_invoice = "generate_invoice" in request.form

    error = None

    cid = current_user.company_id

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
        
        # Validate invoice number and customer in a single connection
        if invoice_number or customer_id is not None:
            conn_check = get_connection()
            try:
                if invoice_number:
                    row = conn_check.execute(
                        "SELECT id FROM sales WHERE invoice_number = ? AND company_id = ?",
                        (invoice_number, cid),
                    ).fetchone()
                    if row is not None:
                        raise ValueError(f"Invoice number {invoice_number} already exists.")

                if customer_id is not None:
                    row = conn_check.execute(
                        "SELECT id FROM customers WHERE id = ? AND company_id = ?",
                        (customer_id, cid),
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
                    "notes": it.get("notes"),
                }
            )

    if not error:
        subtotal = round(sum(li["amount"] for li in parsed_items), 2)
        grand_total = round(subtotal - discount_amount, 2)
        if grand_total < 0:
            grand_total = 0.00

        is_quote = "generate_quote" in request.form
        comp = get_company(cid) or {}
        prefix = comp.get("invoice_prefix") or "INV-"
        
        # Use provided invoice number or generate one
        if is_quote:
            status = 'quote'
            if not invoice_number:
                next_inv = get_next_invoice_number(cid)
                num_part = next_inv.replace(prefix, "") if prefix in next_inv else next_inv
                invoice_number = f"Q-{num_part}"
            elif invoice_number.startswith(prefix):
                invoice_number = "Q-" + invoice_number[len(prefix):]
            elif invoice_number.startswith("AK-"):
                invoice_number = "Q-" + invoice_number[3:]
            elif not invoice_number.startswith("Q-"):
                invoice_number = "Q-" + invoice_number
            amount_paid = 0
            remaining_amount = grand_total
        else:
            if not invoice_number:
                invoice_number = get_next_invoice_number(cid)

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
                    wid = int(warehouse_id_raw) if warehouse_id_raw else (current_user.warehouse_id or 1)
                    cur = conn.execute("SELECT p.name, COALESCE((SELECT stock_quantity FROM warehouse_inventory WHERE product_id = p.id AND warehouse_id = ? AND company_id = ?), 0) as stock_quantity FROM products p WHERE p.id = ? AND p.company_id = ?", (wid, cid, product_id, cid))
                    row = cur.fetchone()
                    if row is None:
                        raise ValueError("One or more selected products are invalid.")
                    stock_quantity = float(row["stock_quantity"] or 0)
                    product_name = row["name"] or "Unknown Product"
                    if stock_quantity + 1e-9 < qty_total:
                        if getattr(current_user, 'role', '') != 'admin':
                            raise ValueError(f"Insufficient stock for {product_name} (requested {qty_total}, available {stock_quantity}).")

            try:
                salesman_id = int(salesman_id_raw) if salesman_id_raw else current_user.id
            except ValueError:
                salesman_id = current_user.id
                
            wid = int(warehouse_id_raw) if warehouse_id_raw else (current_user.warehouse_id or 1)
            wh_row = conn.execute("SELECT commission_applies FROM warehouses WHERE id = ? AND company_id = ?", (wid, cid)).fetchone()
            commission_applies = int(wh_row["commission_applies"] or 0) if wh_row else 0
            
            commission_amount = 0
            for li in parsed_items:
                if commission_applies:
                    br_row = conn.execute("SELECT b.commission_rate FROM products p LEFT JOIN brands b ON LOWER(p.brand) = LOWER(b.name) AND (b.company_id = p.company_id OR b.company_id IS NULL) WHERE p.id = ? AND p.company_id = ?", (li["product_id"], cid)).fetchone()
                    item_comm_rate = float(br_row["commission_rate"] or 0) if br_row and br_row["commission_rate"] is not None else 0
                else:
                    item_comm_rate = 0
                li["commission_amount"] = round(li["amount"] * (item_comm_rate / 100), 2)
                commission_amount += li["commission_amount"]
                
            # We don't have a single commission rate anymore, so we store 0
            commission_rate = 0
                
            cur = conn.execute(
                """
                INSERT INTO sales
                    (company_id, invoice_number, customer_id, invoice_date, due_date, terms, payment_type,
                     discount_amount, subtotal, grand_total, notes, status, amount_paid, remaining_amount, salesman_id, warehouse_id, commission_rate, commission_amount)
                VALUES
                    (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    cid,
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
                    wid,
                    commission_rate,
                    commission_amount,
                ),
            )
            sale_id = int(cur.lastrowid)

            for li in parsed_items:
                conn.execute(
                    """
                    INSERT INTO sale_items
                        (company_id, sale_id, product_id, description, qty, rate, amount, cost_price, print_dual_units, packing_multiplier, commission_amount, notes)
                    VALUES
                        (?, ?, ?, ?, ?, ?, ?, COALESCE((SELECT cost_price FROM products WHERE id = ? AND company_id = ?), 0), ?, ?, ?, ?)
                    """,
                    (
                        cid,
                        sale_id,
                        li["product_id"],
                        li["description"],
                        li["qty"],
                        li["rate"],
                        li["amount"],
                        li["product_id"],
                        cid,
                        li["print_dual_units"],
                        li["packing_multiplier"],
                        li["commission_amount"],
                        li.get("notes", None),
                    ),
                )

            # Deduct stock atomically (per product total)
            if not is_quote:
                for product_id, qty_total in qty_total_by_product.items():
                    wid = int(warehouse_id_raw) if warehouse_id_raw else (current_user.warehouse_id or 1)
                    
                    cur_stock = conn.execute("SELECT stock_quantity FROM warehouse_inventory WHERE product_id = ? AND warehouse_id = ? AND company_id = ?", (product_id, wid, cid)).fetchone()
                    old_stock = float(cur_stock["stock_quantity"] or 0) if cur_stock else 0
                    
                    is_admin = getattr(current_user, 'role', '') == 'admin'
                    if is_admin:
                        conn.execute(
                            """
                            INSERT INTO warehouse_inventory (company_id, product_id, warehouse_id, stock_quantity)
                            VALUES (?, ?, ?, ?)
                            ON CONFLICT(warehouse_id, product_id) DO UPDATE SET stock_quantity = warehouse_inventory.stock_quantity - ?
                            """,
                            (cid, product_id, wid, -qty_total, qty_total),
                        )
                    else:
                        upd = conn.execute(
                            """
                            UPDATE warehouse_inventory
                            SET stock_quantity = stock_quantity - ?
                            WHERE product_id = ? AND warehouse_id = ? AND company_id = ? AND stock_quantity >= ?
                            """,
                            (qty_total, product_id, wid, cid, qty_total),
                        )
                        if upd.rowcount == 0:
                            cur = conn.execute(
                                "SELECT name FROM products WHERE id = ? AND company_id = ?",
                                (product_id, cid),
                            )
                            row = cur.fetchone()
                            product_name = row["name"] if row else "Unknown Product"
                            raise ValueError(f"Insufficient stock for {product_name}.")
                    
                    new_stock = old_stock - qty_total
                    conn.execute("""
                        INSERT INTO inventory_history (company_id, product_id, transaction_type, quantity_change, previous_stock, new_stock, reference, warehouse_id)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                    """, (cid, product_id, 'OUT', -qty_total, old_stock, new_stock, f'Invoice #{invoice_number}', wid))

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
            "SELECT id FROM sales WHERE invoice_number = ? AND company_id = ?",
            (invoice_number, current_user.company_id),
        ).fetchone()
        return jsonify({"exists": row is not None})
    finally:
        conn.close()


@app.route("/sales/edit/<int:sale_id>", methods=["GET"])
@admin_required
def sales_edit(sale_id: int):
    cid = current_user.company_id
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
                s.warehouse_id,
                u.username AS salesman_name
            FROM sales s
            LEFT JOIN users u ON u.id = s.salesman_id
            WHERE s.id = ? AND s.company_id = ?
            """,
            (sale_id, cid),
        ).fetchone()
        
        if sale is None:
            flash("Sale not found.", "error")
            return redirect(url_for("sales"))
        
        # Get customer data
        customer = conn.execute(
            "SELECT id, name FROM customers WHERE id = ? AND company_id = ?",
            (sale["customer_id"], cid),
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
                si.notes,
                COALESCE((SELECT stock_quantity FROM warehouse_inventory WHERE product_id = p.id AND warehouse_id = ? AND company_id = ?), 0) AS stock_quantity,
                p.is_open,
                p.unit,
                p.name
            FROM sale_items si
            LEFT JOIN products p ON p.id = si.product_id
            WHERE si.sale_id = ? AND si.company_id = ?
            """,
            (sale["warehouse_id"] or 1, cid, sale_id, cid),
        ).fetchall()
        
        # Convert to dict and add stock quantity
        edit_sale = dict(sale)
        edit_sale["customer_name"] = customer["name"] if customer else ""
        edit_sale["items"] = [dict(item, qty=float(item["qty"])) for item in items]
        print("DEBUG:", edit_sale.get("amount_paid"), edit_sale.get("remaining_amount"))
        
        # Get other data for the form
        customers = conn.execute(
            "SELECT id, name, terms FROM customers WHERE company_id = ? ORDER BY name COLLATE NOCASE",
            (cid,)
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
            LEFT JOIN sale_items si ON si.sale_id = s.id AND si.company_id = s.company_id
            WHERE s.company_id = ?
            GROUP BY s.id, c.name, u.username
            ORDER BY s.invoice_date DESC, s.id DESC
            LIMIT 10
            """,
            (cid,)
        ).fetchall()
        
        # Get users for dropdown
        users_rows = conn.execute("SELECT id, username, role FROM users WHERE company_id = ? AND is_active = 1 ORDER BY username", (cid,)).fetchall()
        users_list = [dict(r) for r in users_rows]
        
        # Get warehouses
        warehouses = conn.execute("SELECT id, name FROM warehouses WHERE company_id = ? ORDER BY name", (cid,)).fetchall()
        
    finally:
        conn.close()
    
    return render_template(
        "sales.html",
        customers=[dict(c) for c in customers],
        recent_sales=[dict(r) for r in recent_sales],
        all_users=users_list,
        warehouses=[dict(w) for w in warehouses],
        next_invoice_number=get_next_invoice_number(cid),
        today=date.today().isoformat(),
        edit_mode=True,
        edit_sale=edit_sale,
    )


@app.route("/sales/update/<int:sale_id>", methods=["POST"])
@admin_required
def sales_update(sale_id: int):
    cid = current_user.company_id if hasattr(current_user, "company_id") and current_user.company_id else 1
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
    warehouse_id_raw = (request.form.get("warehouse_id") or "").strip()

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
        
        # Validate invoice number and customer in a single connection
        if invoice_number or customer_id is not None:
            conn_check = get_connection()
            try:
                if invoice_number:
                    row = conn_check.execute(
                        "SELECT id FROM sales WHERE invoice_number = ? AND id != ? AND company_id = ?",
                        (invoice_number, sale_id, cid),
                    ).fetchone()
                    if row is not None:
                        raise ValueError(f"Invoice number {invoice_number} already exists.")

                if customer_id is not None:
                    row = conn_check.execute(
                        "SELECT id FROM customers WHERE id = ? AND company_id = ?",
                        (customer_id, cid),
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
                    "notes": it.get("notes"),
                }
            )

    if not error:
        subtotal = round(sum(li["amount"] for li in parsed_items), 2)
        grand_total = round(subtotal - discount_amount, 2)
        if grand_total < 0:
            grand_total = 0.00

        is_quote = "generate_quote" in request.form

        # Calculate amount_paid and remaining_amount based on payment_type
        if is_quote:
            amount_paid = 0
            remaining_amount = grand_total
            status = 'quote'
        else:
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

            sale_info = conn.execute("SELECT warehouse_id, status FROM sales WHERE id = ? AND company_id = ?", (sale_id, cid)).fetchone()
            if not sale_info:
                raise ValueError("Sale not found.")
            was_quote = (sale_info["status"] == "quote")

            # Get old sale items to restore stock
            old_items = conn.execute(
                """
                SELECT product_id, qty, COALESCE(packing_multiplier, 1.0) as packing_multiplier
                FROM sale_items
                WHERE sale_id = ?
                """,
                (sale_id,),
            ).fetchall()

            try:
                salesman_id = int(salesman_id_raw) if salesman_id_raw else current_user.id
            except ValueError:
                salesman_id = current_user.id
                
            old_wid = int(sale_info["warehouse_id"]) if sale_info and sale_info["warehouse_id"] else (current_user.warehouse_id or 1)
            new_wid = int(warehouse_id_raw) if warehouse_id_raw else old_wid

            # Calculate old stock requirements
            old_qty_by_product = defaultdict(float)
            if not was_quote:
                for item in old_items:
                    old_qty_by_product[item["product_id"]] += float(item["qty"]) * float(item["packing_multiplier"])

            # Calculate new stock requirements
            new_qty_by_product = defaultdict(float)
            for li in parsed_items:
                new_qty_by_product[li["product_id"]] += li["qty"] * li["packing_multiplier"]

            # Compute net changes and check availability
            net_deductions = {}
            all_products = set(old_qty_by_product.keys()) | set(new_qty_by_product.keys())
            
            for product_id in all_products:
                old_qty = old_qty_by_product.get(product_id, 0.0)
                new_qty = new_qty_by_product.get(product_id, 0.0)
                net_deduct = new_qty - old_qty
                
                if net_deduct != 0:
                    net_deductions[product_id] = net_deduct
                    
                cur = conn.execute("SELECT name FROM products WHERE id = ? AND company_id = ?", (product_id, cid))
                row = cur.fetchone()
                if row is None:
                    raise ValueError("One or more selected products are invalid.")
                product_name = row["name"] or "Unknown Product"

                if not is_quote:
                    if old_wid == new_wid:
                        if net_deduct > 0:
                            cur = conn.execute("SELECT stock_quantity FROM warehouse_inventory WHERE product_id = ? AND warehouse_id = ?", (product_id, new_wid))
                            wh_row = cur.fetchone()
                            stock_quantity = float(wh_row["stock_quantity"] or 0) if wh_row else 0.0
                            if stock_quantity + 1e-9 < net_deduct:
                                raise ValueError(f"Insufficient stock for {product_name} (requested additional {net_deduct}, available {stock_quantity}).")
                    else:
                        if new_qty > 0:
                            cur = conn.execute("SELECT stock_quantity FROM warehouse_inventory WHERE product_id = ? AND warehouse_id = ?", (product_id, new_wid))
                            wh_row = cur.fetchone()
                            stock_quantity = float(wh_row["stock_quantity"] or 0) if wh_row else 0.0
                            if stock_quantity + 1e-9 < new_qty:
                                raise ValueError(f"Insufficient stock for {product_name} (requested {new_qty}, available {stock_quantity}).")

            # If converting a quote to a sale, assign sequential tenant invoice number
            if was_quote and not is_quote:
                company = conn.execute("SELECT invoice_prefix FROM companies WHERE id = ?", (cid,)).fetchone()
                prefix = company["invoice_prefix"] if company and company["invoice_prefix"] else "INV-"
                if invoice_number and invoice_number.startswith("Q-"):
                    potential_invoice_num = prefix + invoice_number[2:]
                    exists = conn.execute("SELECT 1 FROM sales WHERE invoice_number = ? AND id != ? AND company_id = ?", (potential_invoice_num, sale_id, cid)).fetchone()
                    if not exists:
                        invoice_number = potential_invoice_num
                    else:
                        invoice_number = get_next_invoice_number(cid)
                else:
                    invoice_number = get_next_invoice_number(cid)

            # Calculate commission for the updated sale
            wh_row = conn.execute("SELECT commission_applies FROM warehouses WHERE id = ? AND company_id = ?", (new_wid, cid)).fetchone()
            commission_applies = int(wh_row["commission_applies"] or 0) if wh_row else 0
            
            commission_amount = 0
            for li in parsed_items:
                if commission_applies:
                    br_row = conn.execute(
                        "SELECT b.commission_rate FROM products p LEFT JOIN brands b ON LOWER(p.brand) = LOWER(b.name) AND b.company_id = ? WHERE p.id = ? AND p.company_id = ?",
                        (cid, li["product_id"], cid),
                    ).fetchone()
                    item_comm_rate = float(br_row["commission_rate"] or 0) if br_row and br_row["commission_rate"] is not None else 0
                else:
                    item_comm_rate = 0
                li["commission_amount"] = round(li["amount"] * (item_comm_rate / 100), 2)
                commission_amount += li["commission_amount"]

            conn.execute(
                """
                UPDATE sales
                SET invoice_number = ?, customer_id = ?, invoice_date = ?, due_date = ?,
                    terms = ?, payment_type = ?, discount_amount = ?, subtotal = ?,
                    grand_total = ?, notes = ?, status = ?, amount_paid = ?, remaining_amount = ?, salesman_id = ?, warehouse_id = ?, commission_amount = ?
                WHERE id = ? AND company_id = ?
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
                    new_wid,
                    commission_amount,
                    sale_id,
                    cid,
                ),
            )

            # Delete old sale items
            conn.execute("DELETE FROM sale_items WHERE sale_id = ?", (sale_id,))

            # Insert new sale items
            for li in parsed_items:
                conn.execute(
                    """
                    INSERT INTO sale_items
                        (sale_id, product_id, description, qty, rate, amount, cost_price, print_dual_units, packing_multiplier, commission_amount, notes, company_id)
                    VALUES
                        (?, ?, ?, ?, ?, ?, COALESCE((SELECT cost_price FROM products WHERE id = ? AND company_id = ?), 0), ?, ?, ?, ?, ?)
                    """,
                    (
                        sale_id,
                        li["product_id"],
                        li["description"],
                        li["qty"],
                        li["rate"],
                        li["amount"],
                        li["product_id"],
                        cid,
                        li["print_dual_units"],
                        li["packing_multiplier"],
                        li["commission_amount"],
                        li.get("notes", None),
                        cid,
                    ),
                )

            # Apply stock changes depending on warehouse change
            sale_info_stock = conn.execute("SELECT invoice_number FROM sales WHERE id = ? AND company_id = ?", (sale_id, cid)).fetchone()
            invoice_number = sale_info_stock["invoice_number"] if sale_info_stock else str(sale_id)
            
            # If we are keeping it as a quote, do NOT touch inventory
            if not is_quote:
                if old_wid == new_wid:
                    for product_id, net_deduct in net_deductions.items():
                        if net_deduct == 0:
                            continue
                        cur = conn.execute("SELECT stock_quantity FROM warehouse_inventory WHERE product_id = ? AND warehouse_id = ?", (product_id, new_wid))
                        row = cur.fetchone()
                        old_stock = float(row["stock_quantity"] or 0) if row else 0

                        if net_deduct > 0:
                            is_admin = getattr(current_user, 'role', '') == 'admin'
                            if is_admin:
                                conn.execute(
                                    """
                                    INSERT INTO warehouse_inventory (product_id, warehouse_id, stock_quantity, company_id)
                                    VALUES (?, ?, ?, ?)
                                    ON CONFLICT(warehouse_id, product_id) DO UPDATE SET stock_quantity = warehouse_inventory.stock_quantity - ?
                                    """,
                                    (product_id, new_wid, -net_deduct, cid, net_deduct),
                                )
                            else:
                                upd = conn.execute(
                                    """
                                    UPDATE warehouse_inventory
                                    SET stock_quantity = stock_quantity - ?
                                    WHERE product_id = ? AND warehouse_id = ? AND stock_quantity >= ?
                                    """,
                                    (net_deduct, product_id, new_wid, net_deduct - 1e-9),
                                )
                                if upd.rowcount == 0:
                                    raise ValueError("Insufficient stock during update.")
                        else:
                            conn.execute(
                                """
                                INSERT INTO warehouse_inventory (product_id, warehouse_id, stock_quantity, company_id)
                                VALUES (?, ?, ?, ?)
                                ON CONFLICT(warehouse_id, product_id) DO UPDATE SET stock_quantity = warehouse_inventory.stock_quantity - ?
                                """,
                                (product_id, new_wid, -net_deduct, cid, net_deduct),
                            )
                        
                        new_stock = old_stock - net_deduct
                        trans_type = 'OUT' if net_deduct > 0 else 'IN'
                        qty_change = -net_deduct if net_deduct > 0 else abs(net_deduct)
                        
                        conn.execute("""
                            INSERT INTO inventory_history (product_id, transaction_type, quantity_change, previous_stock, new_stock, reference, warehouse_id, company_id)
                            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                        """, (product_id, trans_type, qty_change, old_stock, new_stock, f'Invoice #{invoice_number} Edit', new_wid, cid))
                else:
                    # Warehouse changed. Restore all old items to old_wid, deduct all new items from new_wid.
                    # 1. Restore old
                    for product_id, qty in old_qty_by_product.items():
                        if qty <= 0: continue
                        cur = conn.execute("SELECT stock_quantity FROM warehouse_inventory WHERE product_id = ? AND warehouse_id = ?", (product_id, old_wid))
                        row = cur.fetchone()
                        old_stock = float(row["stock_quantity"] or 0) if row else 0
                        
                        conn.execute(
                            """
                            INSERT INTO warehouse_inventory (product_id, warehouse_id, stock_quantity, company_id)
                            VALUES (?, ?, ?, ?)
                            ON CONFLICT(warehouse_id, product_id) DO UPDATE SET stock_quantity = warehouse_inventory.stock_quantity + ?
                            """,
                            (product_id, old_wid, qty, cid, qty),
                        )
                        new_stock = old_stock + qty
                        conn.execute("""
                            INSERT INTO inventory_history (product_id, transaction_type, quantity_change, previous_stock, new_stock, reference, warehouse_id, company_id)
                            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                        """, (product_id, 'IN', qty, old_stock, new_stock, f'Invoice #{invoice_number} Edit (Restored)', old_wid, cid))
                        
                    # 2. Deduct new
                    for product_id, qty in new_qty_by_product.items():
                        if qty <= 0: continue
                        cur = conn.execute("SELECT stock_quantity FROM warehouse_inventory WHERE product_id = ? AND warehouse_id = ?", (product_id, new_wid))
                        row = cur.fetchone()
                        old_stock = float(row["stock_quantity"] or 0) if row else 0
                        
                        is_admin = getattr(current_user, 'role', '') == 'admin'
                        if is_admin:
                            conn.execute(
                                """
                                INSERT INTO warehouse_inventory (product_id, warehouse_id, stock_quantity, company_id)
                                VALUES (?, ?, ?, ?)
                                ON CONFLICT(warehouse_id, product_id) DO UPDATE SET stock_quantity = warehouse_inventory.stock_quantity - ?
                                """,
                                (product_id, new_wid, -qty, cid, qty),
                            )
                        else:
                            upd = conn.execute(
                                """
                                UPDATE warehouse_inventory
                                SET stock_quantity = stock_quantity - ?
                                WHERE product_id = ? AND warehouse_id = ? AND stock_quantity >= ?
                                """,
                                (qty, product_id, new_wid, qty - 1e-9),
                            )
                            if upd.rowcount == 0:
                                raise ValueError("Insufficient stock in new warehouse.")
                            
                        new_stock = old_stock - qty
                        conn.execute("""
                            INSERT INTO inventory_history (product_id, transaction_type, quantity_change, previous_stock, new_stock, reference, warehouse_id, company_id)
                            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                        """, (product_id, 'OUT', -qty, old_stock, new_stock, f'Invoice #{invoice_number} Edit', new_wid, cid))

            conn.commit()
        except Exception as e:
            conn.rollback()
            error = str(e)
        finally:
            conn.close()

    if error:
        flash(error, "error")
        return redirect(url_for("sales_edit", sale_id=sale_id))

    if generate_invoice or "generate_quote" in request.form:
        return redirect(url_for("sales_invoice_pdf", id=sale_id))

    flash("Sale updated successfully.", "success")
    return redirect(url_for("sales"))


@app.route("/sales/<int:sale_id>/details", methods=["GET"])
@login_required
def sale_details(sale_id: int):
    cid = current_user.company_id if hasattr(current_user, "company_id") and current_user.company_id else 1
    is_admin = getattr(current_user, 'role', '') == 'admin'
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
                s.commission_amount,
                s.salesman_id,
                c.name as customer_name,
                u.username as salesman_name,
                (SELECT COALESCE(SUM((si.qty * COALESCE(si.packing_multiplier, 1.0) * si.cost_price) + COALESCE(si.commission_amount, 0)), 0) FROM sale_items si WHERE si.sale_id = s.id) as total_cost
            FROM sales s
            LEFT JOIN customers c ON c.id = s.customer_id
            LEFT JOIN users u ON u.id = s.salesman_id
            WHERE s.id = ? AND s.company_id = ?
            """,
            (sale_id, cid),
        ).fetchone()
        
        if not sale:
            return jsonify({"error": "Sale not found"}), 404

        if not is_admin and sale["salesman_id"] != current_user.id:
            return jsonify({"error": "Unauthorized"}), 403
        
        # Get sale items
        items = conn.execute(
            """
            SELECT 
                description,
                qty,
                rate,
                amount,
                commission_amount
            FROM sale_items
            WHERE sale_id = ?
            ORDER BY id
            """,
            (sale_id,),
        ).fetchall()
        
        rev = float(sale["grand_total"] or 0)
        cost = float(sale["total_cost"] or 0)

        # Commercial privacy per ADR 0003
        if is_admin:
            profit_margin = round(((rev - cost) / rev * 100), 2) if rev > 0 else 0
            profit_amount = round(rev - cost, 2)
            total_cost = cost
        else:
            profit_margin = None
            profit_amount = None
            total_cost = None

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
            "commission_amount": sale["commission_amount"],
            "profit_margin": profit_margin,
            "profit_amount": profit_amount,
            "total_cost": total_cost,
            "items": [dict(item) for item in items]
        })
    finally:
        conn.close()


@app.route("/sales/by-invoice/<invoice_number>", methods=["GET"])
@admin_required
def sale_by_invoice(invoice_number: str):
    cid = current_user.company_id if hasattr(current_user, "company_id") and current_user.company_id else 1
    conn = get_connection()
    try:
        # Get sale details by invoice number scoped to company
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
            WHERE s.invoice_number = ? AND s.company_id = ?
            """,
            (invoice_number, cid),
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
                WHERE invoice_number = ? AND company_id = ?
            )
            ORDER BY si.id
            """,
            (invoice_number, cid),
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
    cid = current_user.company_id if hasattr(current_user, "company_id") and current_user.company_id else 1
    conn = get_connection()
    try:
        sale = conn.execute(
            """
            SELECT
                s.id,
                s.invoice_number,
                s.customer_id,
                s.salesman_id,
                s.company_id
            FROM sales s
            WHERE s.id = ? AND s.company_id = ?
            """,
            (id, cid),
        ).fetchone()
        if sale is None:
            return Response("Sale not found", status=404)
        
        if current_user.role != 'admin' and sale["salesman_id"] != current_user.id:
            return Response("Unauthorized", status=403)

        customer = conn.execute(
            """
            SELECT id, name, bill_address, ship_address
            FROM customers
            WHERE id = ? AND company_id = ?
            """,
            (sale["customer_id"], cid),
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
    filename = f"{invoice_number}.pdf" if invoice_number else f"invoice-{id}.pdf"

    resp = Response(pdf_bytes, mimetype="application/pdf")
    resp.headers["Content-Disposition"] = f'inline; filename="{filename}"'
    return resp


@app.route("/sales/<int:sale_id>/mark_sale", methods=["POST"])
@login_required
def sales_mark_sale(sale_id: int):
    cid = current_user.company_id if hasattr(current_user, "company_id") and current_user.company_id else 1
    conn = get_connection()
    try:
        conn.execute("BEGIN")
        sale = conn.execute("SELECT * FROM sales WHERE id = ? AND company_id = ?", (sale_id, cid)).fetchone()
        if not sale:
            conn.rollback()
            return jsonify({"success": False, "message": "Sale not found"})
        
        if sale["status"] != "quote":
            conn.rollback()
            return jsonify({"success": False, "message": "Only quotes can be marked as sales."})

        # Generate actual invoice number using company's prefix
        quote_invoice_num = sale["invoice_number"]
        company = conn.execute("SELECT invoice_prefix FROM companies WHERE id = ?", (cid,)).fetchone()
        prefix = company["invoice_prefix"] if company and company["invoice_prefix"] else "INV-"
        if quote_invoice_num and quote_invoice_num.startswith("Q-"):
            potential_invoice_num = prefix + quote_invoice_num[2:]
            exists = conn.execute("SELECT 1 FROM sales WHERE invoice_number = ? AND company_id = ?", (potential_invoice_num, cid)).fetchone()
            if not exists:
                invoice_number = potential_invoice_num
            else:
                invoice_number = get_next_invoice_number(cid)
        else:
            invoice_number = get_next_invoice_number(cid)

        items = conn.execute("SELECT product_id, qty, packing_multiplier FROM sale_items WHERE sale_id = ?", (sale_id,)).fetchall()

        wid = sale["warehouse_id"] or 1

        # Check stock first
        qty_total_by_product = defaultdict(float)
        for it in items:
            packing_multiplier = float(it["packing_multiplier"] or 1.0)
            qty_total_by_product[it["product_id"]] += float(it["qty"]) * packing_multiplier
            
        for product_id, qty_total in qty_total_by_product.items():
            cur = conn.execute("SELECT p.name, COALESCE((SELECT stock_quantity FROM warehouse_inventory WHERE product_id = p.id AND warehouse_id = ?), 0) as stock_quantity FROM products p WHERE p.id = ? AND p.company_id = ?", (wid, product_id, cid))
            row = cur.fetchone()
            if row is None:
                raise ValueError("Invalid product found in quote.")
            stock_quantity = float(row["stock_quantity"] or 0)
            if stock_quantity + 1e-9 < qty_total:
                if getattr(current_user, 'role', '') != 'admin':
                    raise ValueError(f"Insufficient stock for {row['name']}.")

        # Update stock and write history
        for product_id, qty_total in qty_total_by_product.items():
            cur_stock = conn.execute("SELECT stock_quantity FROM warehouse_inventory WHERE product_id = ? AND warehouse_id = ?", (product_id, wid)).fetchone()
            old_stock = float(cur_stock["stock_quantity"] or 0) if cur_stock else 0
            
            is_admin = getattr(current_user, 'role', '') == 'admin'
            if is_admin:
                conn.execute(
                    """
                    INSERT INTO warehouse_inventory (product_id, warehouse_id, stock_quantity, company_id)
                    VALUES (?, ?, ?, ?)
                    ON CONFLICT(warehouse_id, product_id) DO UPDATE SET stock_quantity = warehouse_inventory.stock_quantity - ?
                    """,
                    (product_id, wid, -qty_total, cid, qty_total),
                )
            else:
                upd = conn.execute(
                    """
                    UPDATE warehouse_inventory
                    SET stock_quantity = stock_quantity - ?
                    WHERE product_id = ? AND warehouse_id = ? AND stock_quantity >= ?
                    """,
                    (qty_total, product_id, wid, qty_total)
                )
                if upd.rowcount == 0:
                    raise ValueError("Stock became insufficient during update.")
            
            new_stock = old_stock - qty_total
            conn.execute("""
                INSERT INTO inventory_history (product_id, transaction_type, quantity_change, previous_stock, new_stock, reference, warehouse_id, company_id)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, (product_id, 'OUT', -qty_total, old_stock, new_stock, f'Invoice #{invoice_number}', wid, cid))
            
        # Update sale record to unpaid and new invoice number
        conn.execute(
            """
            UPDATE sales
            SET status = 'unpaid', invoice_number = ?
            WHERE id = ? AND company_id = ?
            """,
            (invoice_number, sale_id, cid)
        )

        data = request.get_json(silent=True) or {}
        amount = float(data.get('amount', 0))
        payment_method = data.get('payment_method', 'Cash')
        notes = data.get('notes', '')

        if amount > 0:
            if amount > float(sale['remaining_amount']):
                raise ValueError("Payment amount exceeds remaining balance.")
            new_amount_paid = float(sale['amount_paid']) + amount
            new_remaining = float(sale['remaining_amount']) - amount
            new_status = 'paid' if new_remaining <= 0.01 else 'partial'
            
            conn.execute('''UPDATE sales 
                          SET amount_paid = ?, remaining_amount = ?, status = ?, payment_type = ?
                          WHERE id = ? AND company_id = ?''',
                       (new_amount_paid, new_remaining, new_status, payment_method.lower(), sale_id, cid))

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
    cid = current_user.company_id if hasattr(current_user, "company_id") and current_user.company_id else 1
    conn = get_connection()
    try:
        conn.execute("BEGIN")

        cur = conn.execute("SELECT invoice_number, warehouse_id FROM sales WHERE id = ? AND company_id = ?", (id, cid))
        row = cur.fetchone()
        if not row:
            conn.rollback()
            flash("Sale not found.", "error")
            return redirect(url_for("sales"))

        items = conn.execute(
            """
            SELECT product_id, qty, COALESCE(packing_multiplier, 1.0) as packing_multiplier
            FROM sale_items
            WHERE sale_id = ?
            """,
            (id,),
        ).fetchall()

        invoice_number = row["invoice_number"] if row else str(id)
        wid = int(row["warehouse_id"]) if row and row["warehouse_id"] else (current_user.warehouse_id or 1)
        
        conn.execute("DELETE FROM sale_items WHERE sale_id = ?", (id,))
        conn.execute("DELETE FROM sales WHERE id = ? AND company_id = ?", (id, cid))

        for it in items:
            cur = conn.execute("SELECT stock_quantity FROM warehouse_inventory WHERE product_id = ? AND warehouse_id = ?", (it["product_id"], wid))
            row = cur.fetchone()
            old_stock = float(row["stock_quantity"] or 0) if row else 0
            restored_qty = float(it["qty"]) * float(it["packing_multiplier"])
            new_stock = old_stock + restored_qty
            
            conn.execute(
                """
                INSERT INTO warehouse_inventory (product_id, warehouse_id, stock_quantity, company_id)
                VALUES (?, ?, ?, ?)
                ON CONFLICT(warehouse_id, product_id) DO UPDATE SET stock_quantity = ?
                """,
                (it["product_id"], wid, new_stock, cid, new_stock),
            )
            
            conn.execute("""
                INSERT INTO inventory_history (product_id, transaction_type, quantity_change, previous_stock, new_stock, reference, warehouse_id, company_id)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, (it["product_id"], 'IN', restored_qty, old_stock, new_stock, f'Invoice #{invoice_number} Deleted', wid, cid))

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
    cid = current_user.company_id if hasattr(current_user, "company_id") and current_user.company_id else 1
    conn = get_connection()
    try:
        data = request.get_json(silent=True) or {}
        amount = float(data.get('amount', 0))
        payment_method = data.get('payment_method', 'Cash')
        notes = data.get('notes', '')

        sale = conn.execute('SELECT * FROM sales WHERE id = ? AND company_id = ?', (sale_id, cid)).fetchone()

        if not sale:
            return jsonify({'success': False, 'error': 'Sale not found'})

        if sale['status'] == 'quote':
            return jsonify({'success': False, 'error': 'Cannot record payments directly on a quotation. Please convert it to a sale first.'})

        if amount <= 0 or amount > float(sale['remaining_amount']):
            return jsonify({'success': False, 'error': 'Invalid amount'})

        new_amount_paid = float(sale['amount_paid']) + amount
        new_remaining = float(sale['remaining_amount']) - amount
        new_status = 'paid' if new_remaining <= 0.01 else 'partial'

        conn.execute('''UPDATE sales 
                      SET amount_paid = ?, remaining_amount = ?, status = ?, payment_type = ?
                      WHERE id = ? AND company_id = ?''',
                   (new_amount_paid, new_remaining, new_status, payment_method.lower(), sale_id, cid))

        conn.commit()
        return jsonify({'success': True})
    except Exception as e:
        conn.rollback()
        return jsonify({'success': False, 'error': str(e)})
    finally:
        conn.close()


@app.route("/reports/stock-distribution/data", methods=["GET"])
@admin_required
def stock_distribution_data():
    cid = current_user.company_id if hasattr(current_user, "company_id") and current_user.company_id else 1
    brand_filter = request.args.get("brand", "").strip()
    stock_level = request.args.get("stock_level", "").strip()
    product_search = request.args.get("product", "").strip()
    low_stock_threshold = float(request.args.get("low_stock_threshold", 5))

    conn = get_connection()
    try:
        warehouses = conn.execute("SELECT id, name FROM warehouses WHERE company_id = ? ORDER BY id", (cid,)).fetchall()
        wh_list = [{"id": w["id"], "name": w["name"]} for w in warehouses]

        query = """
            SELECT 
                p.id, p.name, p.brand, p.cost_price
            FROM products p
            WHERE p.company_id = ?
        """
        params = [cid]
        if brand_filter:
            query += " AND p.brand = ?"
            params.append(brand_filter)
        if product_search:
            query += " AND p.name LIKE ?"
            params.append(f"%{product_search}%")
            
        query += " ORDER BY p.name COLLATE NOCASE"
        
        products = conn.execute(query, params).fetchall()
        
        # Now fetch all inventory for this company's products
        inv_rows = conn.execute(
            """
            SELECT wi.product_id, wi.warehouse_id, wi.stock_quantity
            FROM warehouse_inventory wi
            JOIN products p ON p.id = wi.product_id
            WHERE p.company_id = ?
            """,
            (cid,)
        ).fetchall()
        
        inv_map = {} # product_id -> warehouse_id -> qty
        for r in inv_rows:
            pid = r["product_id"]
            wid = r["warehouse_id"]
            qty = float(r["stock_quantity"] or 0)
            if pid not in inv_map:
                inv_map[pid] = {}
            inv_map[pid][wid] = qty
            
        results = []
        for p in products:
            pid = p["id"]
            p_inv = inv_map.get(pid, {})
            total_stock = sum(p_inv.values())
            
            # Apply stock level filter
            if stock_level == "low" and (total_stock <= 0 or total_stock > low_stock_threshold):
                continue
            if stock_level == "no_stock" and total_stock > 0:
                continue
            if stock_level == "in_stock" and total_stock <= 0:
                continue
                
            total_value = total_stock * float(p["cost_price"] or 0)
            
            stocks = {}
            for w in wh_list:
                stocks[str(w["id"])] = p_inv.get(w["id"], 0)
                
            results.append({
                "id": pid,
                "name": p["name"],
                "brand": p["brand"],
                "cost_price": float(p["cost_price"] or 0),
                "stocks": stocks,
                "total_stock": total_stock,
                "total_value": total_value
            })
            
        return jsonify({
            "warehouses": wh_list,
            "products": results
        })
    finally:
        conn.close()


@app.route("/reports")
@admin_required
def reports():
    cid = current_user.company_id if hasattr(current_user, "company_id") and current_user.company_id else 1
    conn = get_connection()
    try:
        cur_c = conn.execute("SELECT id, name FROM customers WHERE company_id = ? ORDER BY name COLLATE NOCASE", (cid,))
        customers = [dict(r) for r in cur_c.fetchall()]

        cur_p = conn.execute("SELECT id, name FROM products WHERE company_id = ? ORDER BY name COLLATE NOCASE", (cid,))
        products = [dict(r) for r in cur_p.fetchall()]

        cur_b = conn.execute("SELECT DISTINCT brand FROM products WHERE company_id = ? AND brand IS NOT NULL AND brand != '' ORDER BY brand COLLATE NOCASE", (cid,))
        brands = [r["brand"] for r in cur_b.fetchall()]

        cur_s = conn.execute("SELECT id, name FROM suppliers WHERE company_id = ? ORDER BY name COLLATE NOCASE", (cid,))
        suppliers = [dict(r) for r in cur_s.fetchall()]

        cur_w = conn.execute("SELECT id, name FROM warehouses WHERE company_id = ? ORDER BY name COLLATE NOCASE", (cid,))
        warehouses = [dict(r) for r in cur_w.fetchall()]
    finally:
        conn.close()

    return render_template(
        "reports.html",
        customers=customers,
        products=products,
        brands=brands,
        suppliers=suppliers,
        warehouses=warehouses
    )



def parse_date_filters(conditions, params):
    cid = current_user.company_id if hasattr(current_user, "company_id") and current_user.company_id else 1
    conditions.append("s.company_id = ?")
    params.append(cid)
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
              COALESCE(SUM((si.qty * COALESCE(si.packing_multiplier, 1.0) * si.cost_price) + COALESCE(si.commission_amount, 0)), 0) as total_cost,
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
                COALESCE(SUM((si.qty * COALESCE(si.packing_multiplier, 1.0) * si.cost_price) + COALESCE(si.commission_amount, 0)), 0) as total_cost
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
                COALESCE(SUM((si.qty * COALESCE(si.packing_multiplier, 1.0) * si.cost_price) + COALESCE(si.commission_amount, 0)), 0) as total_cost,
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

@app.route("/reports/commission", methods=["GET"])
@admin_required
def reports_commission():
    conditions = ["s.customer_id IS NOT NULL"]
    params = []
    parse_date_filters(conditions, params)

    brand = (request.args.get("brand") or "").strip()
    if brand:
        conditions.append("p.brand = ?")
        params.append(brand)
        
    salesman_id = (request.args.get("salesman_id") or "").strip()
    if salesman_id and salesman_id != "all":
        try:
            conditions.append("s.salesman_id = ?")
            params.append(int(salesman_id))
        except ValueError:
            pass

    where_sql = " AND ".join(conditions)

    conn = get_connection()
    try:
        rows = conn.execute(
            f'''
            SELECT 
              LOWER(COALESCE(u.username, 'admin')) as salesman_name,
              COALESCE(SUM(si.commission_amount), 0) as commission_amount
            FROM sales s
            LEFT JOIN users u ON u.id = s.salesman_id
            JOIN sale_items si ON si.sale_id = s.id
            JOIN products p ON p.id = si.product_id
            WHERE {where_sql}
            GROUP BY LOWER(COALESCE(u.username, 'admin'))
            ORDER BY commission_amount DESC
            ''',
            params,
        ).fetchall()
    finally:
        conn.close()

    result = []
    for r in rows:
        result.append({
            "salesman_name": "Admin" if r["salesman_name"] == "admin" else r["salesman_name"].title(),
            "commission_amount": float(r["commission_amount"] or 0)
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
              COALESCE(SUM((si.qty * COALESCE(si.packing_multiplier, 1.0) * si.cost_price) + COALESCE(si.commission_amount, 0)), 0) as total_cost,
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
        
    warehouse_id = (request.args.get("warehouse_id") or "").strip()
    
    stock_column = "p.stock_quantity as current_stock"
    if warehouse_id and warehouse_id != "all":
        conditions.append("s.warehouse_id = ?")
        params.append(int(warehouse_id))
        stock_column = f"COALESCE((SELECT stock_quantity FROM warehouse_inventory WHERE product_id = p.id AND warehouse_id = {int(warehouse_id)}), 0) as current_stock"
        
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
                COALESCE(SUM((si.qty * COALESCE(si.packing_multiplier, 1.0) * si.cost_price) + COALESCE(si.commission_amount, 0)), 0) as total_cost,
                {stock_column}
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
    cid = current_user.company_id if hasattr(current_user, "company_id") and current_user.company_id else 1
    conditions = [
        "ih.transaction_type = 'IN'",
        "ih.reference IN ('Initial Stock', 'Initial Stock (Legacy)', 'Manual Edit', 'Manual Edit (Edit Product)')",
        "p.company_id = ?",
    ]
    params = [cid]
    
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
                supplier_id,
                supplier_name,
                SUM(total_added) as total_added,
                SUM(total_value) as total_value,
                SUM(current_stock) as total_remaining,
                SUM(current_stock * cost_price) as value_remaining
            FROM (
                SELECT
                    p.id,
                    s.id AS supplier_id,
                    COALESCE(s.name, 'Untagged') AS supplier_name,
                    COALESCE(SUM(ih.quantity_change), 0) AS total_added,
                    COALESCE(SUM(ih.quantity_change * p.cost_price), 0) AS total_value,
                    p.stock_quantity AS current_stock,
                    p.cost_price AS cost_price
                FROM inventory_history ih
                JOIN products p ON p.id = ih.product_id
                LEFT JOIN suppliers s ON s.id = p.supplier_id
                WHERE {where_sql}
                GROUP BY p.id, s.id, COALESCE(s.name, 'Untagged'), p.stock_quantity, p.cost_price
            )
            GROUP BY supplier_id, supplier_name
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
                p.stock_quantity AS quantity_remaining,
                (p.stock_quantity * p.cost_price) AS value_remaining
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
            "supplier_id": r["supplier_id"],
            "supplier_name": r["supplier_name"],
            "total_added": float(r["total_added"] or 0),
            "total_value": float(r["total_value"] or 0),
            "quantity_remaining": float(r["total_remaining"] or 0),
            "value_remaining": float(r["value_remaining"] or 0)
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
            "quantity_remaining": float(r["quantity_remaining"] or 0),
            "value_remaining": float(r["value_remaining"] or 0)
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


@app.route("/reports/supplier-purchases/<int:supplier_id>", methods=["GET"])
@admin_required
def reports_supplier_purchases(supplier_id):
    cid = current_user.company_id if hasattr(current_user, "company_id") and current_user.company_id else 1
    date_from = request.args.get("date_from", "").strip()
    date_to = request.args.get("date_to", "").strip()
    
    conditions = ["p.supplier_id = ?", "p.company_id = ?"]
    params = [supplier_id, cid]
    
    if date_from:
        conditions.append("date(p.purchase_date) >= ?")
        params.append(date_from)
    if date_to:
        conditions.append("date(p.purchase_date) <= ?")
        params.append(date_to)
        
    where_sql = " AND ".join(conditions)
    
    conn = get_connection()
    try:
        rows = conn.execute(f'''
            SELECT 
                p.id,
                p.purchase_date,
                p.reference_number,
                p.grand_total,
                p.remaining_amount,
                p.status,
                COALESCE(SUM(pi.qty), 0) as total_qty,
                COUNT(DISTINCT pi.product_id) as num_products
            FROM purchases p
            LEFT JOIN purchase_items pi ON pi.purchase_id = p.id
            WHERE {where_sql}
            GROUP BY p.id
            ORDER BY p.purchase_date DESC, p.id DESC
        ''', params).fetchall()
        
        result = []
        for r in rows:
            result.append({
                "id": r["id"],
                "purchase_date": r["purchase_date"],
                "reference_number": r["reference_number"],
                "grand_total": r["grand_total"],
                "remaining_amount": r["remaining_amount"],
                "status": r["status"],
                "total_qty": r["total_qty"],
                "num_products": r["num_products"]
            })
            
        return jsonify(result)
    finally:
        conn.close()


@app.route("/reports/profit")
@admin_required
def reports_profit():
    cid = current_user.company_id if hasattr(current_user, "company_id") and current_user.company_id else 1
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
                COALESCE(SUM((si.qty * COALESCE(si.packing_multiplier, 1.0) * si.cost_price) + COALESCE(si.commission_amount, 0)), 0) as total_cost
            FROM sales s
            JOIN sale_items si ON si.sale_id = s.id
            JOIN products p ON si.product_id = p.id
            WHERE s.company_id = ?
        '''
        params = [cid]
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
                  COALESCE(SUM((si.qty * COALESCE(si.packing_multiplier, 1.0) * si.cost_price) + COALESCE(si.commission_amount, 0)), 0) as total_cost,
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
                    COALESCE(SUM((si.qty * COALESCE(si.packing_multiplier, 1.0) * si.cost_price) + COALESCE(si.commission_amount, 0)), 0) as total_cost
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
                    COALESCE(SUM((si.qty * COALESCE(si.packing_multiplier, 1.0) * si.cost_price) + COALESCE(si.commission_amount, 0)), 0) as total_cost,
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
                    COALESCE(SUM((si.qty * COALESCE(si.packing_multiplier, 1.0) * si.cost_price) + COALESCE(si.commission_amount, 0)), 0) as total_cost,
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
    cid = current_user.company_id if hasattr(current_user, "company_id") and current_user.company_id else 1
    conn = get_connection()
    try:
        users = conn.execute("""
            SELECT u.id, u.username, u.role, u.is_active, u.warehouse_id, w.name as warehouse_name,
                   (SELECT COUNT(*) FROM sales WHERE salesman_id = u.id AND company_id = ?) as sales_count,
                   (SELECT COALESCE(SUM(grand_total), 0) FROM sales WHERE salesman_id = u.id AND company_id = ?) as sales_volume
            FROM users u 
            LEFT JOIN warehouses w ON u.warehouse_id = w.id
            WHERE u.company_id = ?
            ORDER BY u.id ASC
        """, (cid, cid, cid)).fetchall()
        warehouses = conn.execute("SELECT id, name FROM warehouses WHERE company_id = ? ORDER BY name", (cid,)).fetchall()
        user_dicts = [dict(u) for u in users]
        total_users = len(user_dicts)
        active_users = sum(1 for u in user_dicts if u.get('is_active') == 1)
        salesmen_count = sum(1 for u in user_dicts if u.get('role') == 'salesman')
        admins_count = sum(1 for u in user_dicts if u.get('role') == 'admin')

        return render_template(
            "users.html",
            users=user_dicts,
            warehouses=[dict(w) for w in warehouses],
            total_users=total_users,
            active_users=active_users,
            salesmen_count=salesmen_count,
            admins_count=admins_count
        )
    finally:
        conn.close()

@app.route("/users/add", methods=["POST"])
@admin_required
def users_add():
    cid = current_user.company_id if hasattr(current_user, "company_id") and current_user.company_id else 1
    username = (request.form.get("username") or "").strip()
    password = (request.form.get("password") or "").strip()
    role = (request.form.get("role") or "salesman").strip()
    if not username or not password:
        return jsonify({"ok": False, "error": "Username and password are required."}), 400
    
    warehouse_id = request.form.get("warehouse_id")
    if not warehouse_id:
        warehouse_id = None
        
    conn = get_connection()
    try:
        if warehouse_id:
            wh_check = conn.execute("SELECT id FROM warehouses WHERE id = ? AND company_id = ?", (warehouse_id, cid)).fetchone()
            if not wh_check:
                return jsonify({"ok": False, "error": "Invalid warehouse selected."}), 400

        conn.execute(
            "INSERT INTO users (username, password_hash, role, warehouse_id, company_id) VALUES (?, ?, ?, ?, ?)",
            (username, generate_password_hash(password, method="pbkdf2:sha256"), role, warehouse_id, cid)
        )
        conn.commit()
        return jsonify({"ok": True})
    except (sqlite3.IntegrityError, Exception) as e:
        if "unique" in str(e).lower() or "duplicate" in str(e).lower():
            return jsonify({"ok": False, "error": "Username already exists."}), 409
        return jsonify({"ok": False, "error": str(e)}), 500
    finally:
        conn.close()

@app.route("/users/toggle_active/<int:user_id>", methods=["POST"])
@admin_required
def users_toggle_active(user_id):
    cid = current_user.company_id if hasattr(current_user, "company_id") and current_user.company_id else 1
    redirect_target = request.referrer or url_for("users_list")
    if user_id == current_user.id:
        flash("You cannot deactivate your own account.", "warning")
        return redirect(redirect_target)

    conn = get_connection()
    try:
        cur = conn.execute("SELECT is_active, username FROM users WHERE id = ? AND company_id = ?", (user_id, cid))
        row = cur.fetchone()
        if not row:
            abort(404)
        new_active = False if row["is_active"] in (1, True, "1") else True
        conn.execute("UPDATE users SET is_active = ? WHERE id = ? AND company_id = ?", (new_active, user_id, cid))
        conn.commit()
        status_txt = "reactivated" if new_active else "suspended"
        flash(f"User account '{row['username']}' {status_txt} successfully.", "success")
    finally:
        conn.close()
    return redirect(redirect_target)

@app.route("/users/edit/<int:user_id>", methods=["POST"])
@admin_required
def users_edit(user_id):
    cid = current_user.company_id if hasattr(current_user, "company_id") and current_user.company_id else 1
    redirect_target = request.referrer or url_for("users_list")
    warehouse_id = request.form.get("warehouse_id")
    if not warehouse_id:
        warehouse_id = None
    role = (request.form.get("role") or "salesman").strip()
    
    conn = get_connection()
    try:
        target_user = conn.execute("SELECT id, role, username FROM users WHERE id = ? AND company_id = ?", (user_id, cid)).fetchone()
        if not target_user:
            abort(404)
        if warehouse_id:
            wh_check = conn.execute("SELECT id FROM warehouses WHERE id = ? AND company_id = ?", (warehouse_id, cid)).fetchone()
            if not wh_check:
                flash("Invalid warehouse selected.", "danger")
                return redirect(redirect_target)
        conn.execute("UPDATE users SET role = ?, warehouse_id = ? WHERE id = ? AND company_id = ?", (role, warehouse_id, user_id, cid))
        conn.commit()
        flash(f"User account '{target_user['username']}' updated successfully.", "success")
        return redirect(redirect_target)
    finally:
        conn.close()

# ---------------------------------------------------------
# WAREHOUSES
# ---------------------------------------------------------
@app.route("/warehouses")
@admin_required
def warehouses_list():
    cid = current_user.company_id if hasattr(current_user, "company_id") and current_user.company_id else 1
    conn = get_connection()
    try:
        warehouses = conn.execute("""
            SELECT w.*,
                   COUNT(DISTINCT wi.product_id) as total_products,
                   COALESCE(SUM(wi.stock_quantity), 0) as total_units,
                   COALESCE(SUM(wi.stock_quantity * p.cost_price), 0) as total_inventory_value
            FROM warehouses w
            LEFT JOIN warehouse_inventory wi ON w.id = wi.warehouse_id
            LEFT JOIN products p ON wi.product_id = p.id AND p.company_id = ?
            WHERE w.company_id = ?
            GROUP BY w.id
            ORDER BY w.name
        """, (cid, cid)).fetchall()
        return render_template("warehouses.html", warehouses=[dict(w) for w in warehouses])
    finally:
        conn.close()

@app.route("/api/warehouse/recent_sales")
@admin_required
def api_warehouse_recent_sales():
    cid = current_user.company_id if hasattr(current_user, "company_id") and current_user.company_id else 1
    warehouse_id = request.args.get("warehouse_id")
    if not warehouse_id:
        return jsonify([])
        
    conn = get_connection()
    try:
        wh = conn.execute("SELECT id FROM warehouses WHERE id = ? AND company_id = ?", (warehouse_id, cid)).fetchone()
        if not wh:
            return jsonify([])
            
        cur = conn.execute("""
            SELECT 
                s.id, s.invoice_number, s.invoice_date, c.name as customer_name,
                s.grand_total, s.status, u.username as salesman_name
            FROM sales s
            LEFT JOIN customers c ON s.customer_id = c.id
            LEFT JOIN users u ON s.salesman_id = u.id
            WHERE s.warehouse_id = ? AND s.company_id = ? AND s.status != 'quote'
            ORDER BY s.invoice_date DESC, s.id DESC
            LIMIT 5
        """, (warehouse_id, cid))
        sales = [dict(row) for row in cur.fetchall()]
        return jsonify(sales)
    finally:
        conn.close()

@app.route("/api/warehouse/inventory")
@admin_required
def api_warehouse_inventory():
    cid = current_user.company_id if hasattr(current_user, "company_id") and current_user.company_id else 1
    warehouse_id = request.args.get("warehouse_id")
    if not warehouse_id:
        return jsonify([])
        
    conn = get_connection()
    try:
        wh = conn.execute("SELECT id FROM warehouses WHERE id = ? AND company_id = ?", (warehouse_id, cid)).fetchone()
        if not wh:
            return jsonify([])

        cur = conn.execute("""
            SELECT 
                p.id as product_id,
                p.name,
                p.brand,
                COALESCE(wi.stock_quantity, 0) as stock_quantity,
                p.cost_price,
                (COALESCE(wi.stock_quantity, 0) * COALESCE(p.cost_price, 0)) as total_value
            FROM products p
            JOIN warehouse_inventory wi ON p.id = wi.product_id AND wi.company_id = ?
            WHERE wi.warehouse_id = ? AND p.company_id = ?
            ORDER BY p.name ASC
        """, (cid, warehouse_id, cid))
        inventory = [dict(row) for row in cur.fetchall()]
        return jsonify(inventory)
    finally:
        conn.close()

@app.route("/warehouses/add", methods=["POST"])
@admin_required
def warehouses_add():
    cid = current_user.company_id if hasattr(current_user, "company_id") and current_user.company_id else 1
    name = (request.form.get("name") or "").strip()
    location = (request.form.get("location") or "").strip()
    commission_applies = 1 if request.form.get("commission_applies") == "1" else 0
    if not name:
        return redirect(url_for("warehouses_list"))
        
    conn = get_connection()
    try:
        # Enforce max_warehouses limit
        co_row = conn.execute("SELECT max_warehouses FROM companies WHERE id = ?", (cid,)).fetchone()
        max_w = co_row["max_warehouses"] if co_row and co_row["max_warehouses"] is not None else 5
        cur_count_row = conn.execute("SELECT COUNT(*) as count FROM warehouses WHERE company_id = ?", (cid,)).fetchone()
        cur_count = cur_count_row["count"] if cur_count_row else 0
        if cur_count >= max_w:
            flash(f"Warehouse limit reached ({max_w}). Please upgrade your plan to add more warehouses.", "error")
            return redirect(url_for("warehouses_list"))

        conn.execute(
            "INSERT INTO warehouses (name, location, commission_applies, company_id) VALUES (?, ?, ?, ?)",
            (name, location, commission_applies, cid)
        )
        conn.commit()
    except (sqlite3.IntegrityError, Exception):
        pass
    finally:
        conn.close()
    return redirect(url_for("warehouses_list"))

@app.route("/warehouses/edit/<int:warehouse_id>", methods=["POST"])
@admin_required
def warehouses_edit(warehouse_id):
    cid = current_user.company_id if hasattr(current_user, "company_id") and current_user.company_id else 1
    name = (request.form.get("name") or "").strip()
    location = (request.form.get("location") or "").strip()
    commission_applies = 1 if request.form.get("commission_applies") == "1" else 0
    if not name:
        return redirect(url_for("warehouses_list"))
        
    conn = get_connection()
    try:
        cur = conn.execute("SELECT id FROM warehouses WHERE id = ? AND company_id = ?", (warehouse_id, cid)).fetchone()
        if not cur:
            abort(404)
        try:
            conn.execute("UPDATE warehouses SET name = ?, location = ?, commission_applies = ? WHERE id = ? AND company_id = ?", (name, location, commission_applies, warehouse_id, cid))
            conn.commit()
        except (sqlite3.IntegrityError, Exception):
            pass
    finally:
        conn.close()
    return redirect(url_for("warehouses_list"))

@app.route("/users/reset_password", methods=["POST"])
@admin_required
def users_reset_password():
    cid = current_user.company_id if hasattr(current_user, "company_id") and current_user.company_id else 1
    user_id = request.form.get("user_id")
    new_password = request.form.get("new_password")
    if not user_id or not new_password:
        return jsonify({"ok": False, "error": "User ID and new password are required."}), 400
    
    conn = get_connection()
    try:
        target_user = conn.execute("SELECT id FROM users WHERE id = ? AND company_id = ?", (user_id, cid)).fetchone()
        if not target_user:
            return jsonify({"ok": False, "error": "User not found."}), 404

        conn.execute(
            "UPDATE users SET password_hash = ? WHERE id = ? AND company_id = ?",
            (generate_password_hash(new_password, method="pbkdf2:sha256"), user_id, cid)
        )
        conn.commit()
        return jsonify({"ok": True})
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500
    finally:
        conn.close()

ALLOWED_LOGO_EXTENSIONS = {"png", "jpg", "jpeg", "webp", "svg"}
MAX_LOGO_BYTES = 2 * 1024 * 1024  # 2MB

@app.route("/settings", methods=["GET", "POST"])
@login_required
@admin_required
def settings_hub():
    cid = current_user.company_id if hasattr(current_user, "company_id") and current_user.company_id else 1
    conn = get_connection()
    try:
        if request.method == "POST":
            form_type = request.form.get("form_type", "company")
            
            if form_type == "company":
                name = (request.form.get("name") or "").strip()
                tax_id = (request.form.get("tax_id") or "").strip()
                bill_address = (request.form.get("bill_address") or "").strip()
                ship_address = (request.form.get("ship_address") or "").strip()
                phone = (request.form.get("phone") or "").strip()
                email = (request.form.get("email") or "").strip()
                currency = (request.form.get("currency") or "$").strip()
                invoice_prefix = (request.form.get("invoice_prefix") or "INV-").strip()
                remove_logo = request.form.get("remove_logo") == "1"

                if not name:
                    flash("Company legal name is required.", "danger")
                    dest = "settings_company" if request.path == "/settings/company" else "settings_hub"
                    return redirect(url_for(dest, tab="company") if dest == "settings_hub" else url_for(dest))

                logo_url = None
                if "logo" in request.files:
                    file = request.files["logo"]
                    if file and file.filename:
                        ext = file.filename.rsplit(".", 1)[-1].lower() if "." in file.filename else ""
                        if ext not in ALLOWED_LOGO_EXTENSIONS:
                            flash("Invalid image format. Allowed extensions: PNG, JPG, JPEG, WEBP, SVG.", "danger")
                            dest = "settings_company" if request.path == "/settings/company" else "settings_hub"
                            return redirect(url_for(dest, tab="company") if dest == "settings_hub" else url_for(dest))
                        
                        content = file.read()
                        if len(content) > MAX_LOGO_BYTES:
                            flash("Logo file exceeds maximum size of 2MB.", "danger")
                            dest = "settings_company" if request.path == "/settings/company" else "settings_hub"
                            return redirect(url_for(dest, tab="company") if dest == "settings_hub" else url_for(dest))
                        
                        safe_filename = f"company_{cid}.{ext}"
                        content_type = f"image/{'svg+xml' if ext == 'svg' else ext}"
                        logo_url = storage.save_company_logo(content, safe_filename, content_type=content_type)

                if logo_url:
                    conn.execute(
                        """
                        UPDATE companies
                        SET name = ?, tax_id = ?, bill_address = ?, ship_address = ?, phone = ?, email = ?, currency = ?, invoice_prefix = ?, logo_url = ?
                        WHERE id = ?
                        """,
                        (name, tax_id, bill_address, ship_address, phone, email, currency, invoice_prefix, logo_url, cid)
                    )
                elif remove_logo:
                    existing_row = conn.execute("SELECT logo_url FROM companies WHERE id = ?", (cid,)).fetchone()
                    if existing_row and existing_row["logo_url"]:
                        storage.delete_company_logo(existing_row["logo_url"])
                    conn.execute(
                        """
                        UPDATE companies
                        SET name = ?, tax_id = ?, bill_address = ?, ship_address = ?, phone = ?, email = ?, currency = ?, invoice_prefix = ?, logo_url = NULL
                        WHERE id = ?
                        """,
                        (name, tax_id, bill_address, ship_address, phone, email, currency, invoice_prefix, cid)
                    )
                else:
                    conn.execute(
                        """
                        UPDATE companies
                        SET name = ?, tax_id = ?, bill_address = ?, ship_address = ?, phone = ?, email = ?, currency = ?, invoice_prefix = ?
                        WHERE id = ?
                        """,
                        (name, tax_id, bill_address, ship_address, phone, email, currency, invoice_prefix, cid)
                    )
                conn.commit()
                flash("Company settings updated successfully.", "success")
                dest = "settings_company" if request.path == "/settings/company" else "settings_hub"
                return redirect(url_for(dest, tab="company") if dest == "settings_hub" else url_for(dest))

            elif form_type == "preferences":
                default_warehouse_id = request.form.get("default_warehouse_id")
                default_warehouse_id = int(default_warehouse_id) if default_warehouse_id and default_warehouse_id.isdigit() else None
                low_stock_threshold = request.form.get("low_stock_threshold", "5")
                try:
                    low_stock_threshold = max(1, int(low_stock_threshold))
                except ValueError:
                    low_stock_threshold = 5
                starting_inv = request.form.get("starting_invoice_number", "1")
                try:
                    starting_inv = max(1, int(starting_inv))
                except ValueError:
                    starting_inv = 1

                conn.execute(
                    """
                    UPDATE companies
                    SET default_warehouse_id = ?, low_stock_threshold = ?, starting_invoice_number = ?
                    WHERE id = ?
                    """,
                    (default_warehouse_id, low_stock_threshold, starting_inv, cid)
                )
                conn.commit()
                flash("Operational preferences updated successfully.", "success")
                return redirect(url_for("settings_hub", tab="preferences"))

            elif form_type == "brochure":
                conn.execute("UPDATE brands SET show_in_brochure = 0 WHERE company_id = ?", (cid,))
                conn.execute("UPDATE products SET show_in_brochure = 0 WHERE company_id = ?", (cid,))
                selected_brands = request.form.getlist("brands")
                selected_products = request.form.getlist("products")
                for b_id in selected_brands:
                    conn.execute("UPDATE brands SET show_in_brochure = 1 WHERE id = ? AND company_id = ?", (b_id, cid))
                for p_id in selected_products:
                    conn.execute("UPDATE products SET show_in_brochure = 1 WHERE id = ? AND company_id = ?", (p_id, cid))
                conn.commit()
                flash("Brochure and catalog settings saved successfully.", "success")
                return redirect(url_for("settings_hub", tab="brochure"))

        active_tab = (request.args.get("tab") or "company").strip().lower()
        if active_tab not in {"company", "users", "brochure", "preferences", "platform"}:
            active_tab = "company"

        if active_tab == "platform" and getattr(current_user, "role", "") != "superadmin":
            flash("Platform governance settings are restricted to SuperAdmin.", "warning")
            return redirect(url_for("settings_hub", tab="company"))

        company_row = conn.execute("SELECT * FROM companies WHERE id = ?", (cid,)).fetchone()
        company = dict(company_row) if company_row else {"id": cid, "name": "Company", "currency": "$", "invoice_prefix": "INV-"}

        # Team / Users
        users = conn.execute("""
            SELECT u.id, u.username, u.role, u.is_active, u.warehouse_id, w.name as warehouse_name
            FROM users u
            LEFT JOIN warehouses w ON u.warehouse_id = w.id
            WHERE u.company_id = ?
            ORDER BY u.id ASC
        """, (cid,)).fetchall()
        user_list = [dict(u) for u in users]

        # Warehouses
        warehouses = [dict(w) for w in conn.execute("SELECT id, name FROM warehouses WHERE company_id = ? ORDER BY name", (cid,)).fetchall()]

        # Brochure brands and products
        brands = [dict(b) for b in conn.execute("SELECT id, name, show_in_brochure FROM brands WHERE company_id = ? ORDER BY name", (cid,)).fetchall()]
        products = [dict(p) for p in conn.execute("SELECT id, name, brand, show_in_brochure FROM products WHERE company_id = ? ORDER BY name", (cid,)).fetchall()]
        products_by_brand = {}
        for p in products:
            b = p["brand"] or "Uncategorized"
            if b not in products_by_brand:
                products_by_brand[b] = []
            products_by_brand[b].append(p)

        # Platform stats for SuperAdmin
        platform_stats = None
        if getattr(current_user, "role", "") == "superadmin":
            total_companies = conn.execute("SELECT COUNT(*) as c FROM companies").fetchone()["c"]
            active_companies = conn.execute("SELECT COUNT(*) as c FROM companies WHERE is_active = TRUE").fetchone()["c"]
            total_platform_users = conn.execute("SELECT COUNT(*) as c FROM users").fetchone()["c"]
            platform_stats = {
                "total_companies": total_companies,
                "active_companies": active_companies,
                "total_platform_users": total_platform_users
            }

        return render_template(
            "settings.html",
            company=company,
            active_tab=active_tab,
            users=user_list,
            warehouses=warehouses,
            brands=brands,
            products_by_brand=products_by_brand,
            platform_stats=platform_stats
        )
    finally:
        conn.close()

@app.route("/settings/company", methods=["GET", "POST"])
@login_required
@admin_required
def settings_company():
    return settings_hub()

@app.route("/superadmin/switch-tenant/<int:company_id>", methods=["GET", "POST"])
@login_required
@superadmin_required
def superadmin_switch_tenant(company_id):
    conn = get_connection()
    try:
        co = conn.execute("SELECT id, name FROM companies WHERE id = ?", (company_id,)).fetchone()
        if not co:
            flash("Target company workspace not found.", "danger")
            return redirect(request.referrer or url_for("superadmin_dashboard"))
        session["active_company_id"] = company_id
        flash(f"Switched active workspace view to '{co['name']}'.", "success")
        return redirect(request.referrer or url_for("dashboard"))
    finally:
        conn.close()

@app.route("/superadmin/switch-tenant/clear", methods=["GET", "POST"])
@login_required
@superadmin_required
def superadmin_clear_tenant_switch():
    session.pop("active_company_id", None)
    flash("Reset workspace view to platform default.", "info")
    return redirect(request.referrer or url_for("superadmin_dashboard"))

@app.route("/superadmin")
@login_required
@superadmin_required
def superadmin_dashboard():
    conn = get_connection()
    try:
        total_companies = conn.execute("SELECT COUNT(*) FROM companies").fetchone()[0]
        # In SQLite 1/0, in Postgres true/false
        active_companies = conn.execute("SELECT COUNT(*) FROM companies WHERE is_active = 1 OR is_active IS TRUE").fetchone()[0]
        total_users = conn.execute("SELECT COUNT(*) FROM users").fetchone()[0]
        total_products = conn.execute("SELECT COUNT(*) FROM products").fetchone()[0]

        sales_agg = conn.execute("SELECT COUNT(*), COALESCE(SUM(grand_total), 0) FROM sales").fetchone()
        total_sales_count = sales_agg[0] if sales_agg else 0
        total_gmv = float(sales_agg[1]) if sales_agg and sales_agg[1] else 0.0

        companies_raw = conn.execute(
            """
            SELECT 
                c.id, c.name, c.slug, c.currency, c.is_active, c.created_at, c.max_warehouses, c.logo_url,
                (SELECT COUNT(*) FROM users u WHERE u.company_id = c.id) AS user_count,
                (SELECT COUNT(*) FROM products p WHERE p.company_id = c.id) AS product_count,
                (SELECT COUNT(*) FROM sales s WHERE s.company_id = c.id) AS sale_count,
                (SELECT COALESCE(SUM(s.grand_total), 0) FROM sales s WHERE s.company_id = c.id) AS gmv_sum
            FROM companies c
            ORDER BY c.id ASC
            """
        ).fetchall()

        companies = [dict(c) for c in companies_raw]

        metrics = {
            "total_companies": total_companies,
            "active_companies": active_companies,
            "inactive_companies": total_companies - active_companies,
            "total_users": total_users,
            "total_products": total_products,
            "total_sales_count": total_sales_count,
            "total_gmv": total_gmv,
        }

        return render_template("superadmin.html", metrics=metrics, companies=companies)
    finally:
        conn.close()


@app.route("/superadmin/company/<int:company_id>/toggle_status", methods=["POST"])
@login_required
@superadmin_required
def superadmin_toggle_company(company_id):
    if company_id == 1:
        flash("Master company (AK Distributors LLC) cannot be deactivated.", "warning")
        return redirect(url_for("superadmin_dashboard"))

    conn = get_connection()
    try:
        co = conn.execute("SELECT id, name, is_active FROM companies WHERE id = ?", (company_id,)).fetchone()
        if not co:
            flash("Company not found.", "danger")
            return redirect(url_for("superadmin_dashboard"))

        curr_active = co["is_active"]
        new_active = False if curr_active in (1, True, "1") else True
        conn.execute("UPDATE companies SET is_active = ? WHERE id = ?", (new_active, company_id))
        conn.commit()

        status_text = "reactivated" if new_active else "deactivated"
        flash(f"Company '{co['name']}' has been {status_text} successfully.", "success")
        return redirect(url_for("superadmin_dashboard"))
    finally:
        conn.close()


@app.route("/superadmin/company/<int:company_id>/update_plan", methods=["POST"])
@login_required
@superadmin_required
def superadmin_update_company_plan(company_id):
    conn = get_connection()
    try:
        max_warehouses = int(request.form.get("max_warehouses", 5))
        if max_warehouses < 1:
            max_warehouses = 1
        conn.execute("UPDATE companies SET max_warehouses = ? WHERE id = ?", (max_warehouses, company_id))
        conn.commit()
        flash("Tenant plan capacity updated successfully.", "success")
        return redirect(url_for("superadmin_dashboard"))
    finally:
        conn.close()

@app.route("/pos")
@login_required
def pos():
    cid = current_user.company_id if hasattr(current_user, "company_id") and current_user.company_id else 1
    conn = get_connection()
    try:
        warehouses = conn.execute("SELECT id, name FROM warehouses WHERE company_id = ? ORDER BY name", (cid,)).fetchall()
        return render_template("catalogue.html", warehouses=[dict(w) for w in warehouses])
    finally:
        conn.close()

@app.route("/pos/submit_order", methods=["POST"])
@login_required
def pos_submit_order():
    cid = current_user.company_id if hasattr(current_user, "company_id") and current_user.company_id else 1
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
    invoice_number = get_next_invoice_number(cid)
    warehouse_id_raw = data.get("warehouse_id")
    wid = int(warehouse_id_raw) if warehouse_id_raw else (current_user.warehouse_id or 1)
    
    conn = get_connection()
    try:
        conn.execute("BEGIN")

        # Create customer if id not provided
        if not customer_id:
            if not customer_name:
                raise ValueError("Customer name is required.")
            cur = conn.execute(
                "INSERT INTO customers (name, bill_address, ship_address, area, state, phone, email, terms, salesman_id, company_id) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (customer_name, customer_bill, customer_ship, customer_area, customer_state, customer_phone, customer_email, customer_terms, current_user.id, cid)
            )
            customer_id = int(cur.lastrowid)
        else:
            customer_id = int(customer_id)
            cust_row = conn.execute("SELECT id FROM customers WHERE id = ? AND company_id = ?", (customer_id, cid)).fetchone()
            if not cust_row:
                raise ValueError("Customer not found.")

        # Parse items and calculate totals
        subtotal = 0
        parsed_items = []
        for it in items:
            product_id = int(it["id"])
            qty = float(it["qty"])
            if qty <= 0:
                continue
            
            if product_id == -1:
                rate = float(it.get("rate", 0))
                amount = round(qty * rate, 2)
                subtotal += amount
                
                parsed_items.append({
                    "product_id": -1,
                    "description": it.get("description", "Open Product"),
                    "qty": qty,
                    "rate": rate,
                    "amount": amount
                })
            else:
                cur = conn.execute("SELECT name, selling_price, cost_price, is_open FROM products WHERE id = ? AND company_id = ?", (product_id, cid))
                row = cur.fetchone()
                if not row:
                    raise ValueError(f"Invalid product ID {product_id}")
                
                if row["is_open"]:
                    rate = float(row["selling_price"] or 0)
                    description = it.get("description", row["name"])
                    pm = float(it.get("packing_multiplier", 1.0))
                else:
                    rate = float(row["selling_price"] or 0)
                    description = row["name"]
                    pm = 1.0
                
                amount = round(qty * rate * pm, 2)
                subtotal += amount
                
                parsed_items.append({
                    "product_id": product_id,
                    "description": description,
                    "qty": qty,
                    "rate": rate,
                    "amount": amount,
                    "packing_multiplier": pm
                })

        if not parsed_items:
            raise ValueError("Cart has no valid items.")

        # Validate stock quantity
        qty_total_by_product = defaultdict(float)
        for li in parsed_items:
            if li["product_id"] != -1:
                qty_total_by_product[li["product_id"]] += li["qty"] * li["packing_multiplier"]
            
        for product_id, qty_total in qty_total_by_product.items():
            cur = conn.execute("SELECT p.name, COALESCE((SELECT stock_quantity FROM warehouse_inventory WHERE product_id = p.id AND warehouse_id = ?), 0) as stock_quantity FROM products p WHERE p.id = ? AND p.company_id = ?", (wid, product_id, cid))
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

        # Fetch commission rate
        wh_row = conn.execute("SELECT commission_applies FROM warehouses WHERE id = ? AND company_id = ?", (wid, cid)).fetchone()
        commission_applies = int(wh_row["commission_applies"] or 0) if wh_row else 0
        
        commission_amount = 0
        for li in parsed_items:
            if commission_applies and li["product_id"] != -1:
                br_row = conn.execute(
                    "SELECT b.commission_rate FROM products p LEFT JOIN brands b ON LOWER(p.brand) = LOWER(b.name) AND b.company_id = ? WHERE p.id = ? AND p.company_id = ?",
                    (cid, li["product_id"], cid),
                ).fetchone()
                item_comm_rate = float(br_row["commission_rate"] or 0) if br_row and br_row["commission_rate"] is not None else 0
            else:
                item_comm_rate = 0
            li["commission_amount"] = round(li["amount"] * (item_comm_rate / 100), 2)
            commission_amount += li["commission_amount"]

        commission_rate = 0

        # Insert sale with company_id
        cur = conn.execute(
            """
            INSERT INTO sales
                (invoice_number, customer_id, invoice_date, due_date, terms, payment_type,
                 subtotal, grand_total, status, amount_paid, remaining_amount, salesman_id, warehouse_id, commission_rate, commission_amount, company_id)
            VALUES
                (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                invoice_number, customer_id, invoice_date, data.get("due_date"), data.get("customer_terms"), payment_type,
                subtotal, grand_total, status, amount_paid, remaining_amount, current_user.id, wid, commission_rate, commission_amount, cid
            )
        )
        sale_id = int(cur.lastrowid)

        # Insert items and deduct stock
        for li in parsed_items:
            conn.execute(
                """
                INSERT INTO sale_items
                    (sale_id, product_id, description, qty, rate, amount, cost_price, packing_multiplier, commission_amount, notes, company_id)
                VALUES
                    (?, ?, ?, ?, ?, ?, COALESCE((SELECT cost_price FROM products WHERE id = ? AND company_id = ?), 0.0), ?, ?, ?, ?)
                """,
                (
                    sale_id, 
                    None if li["product_id"] == -1 else li["product_id"], 
                    li["description"], 
                    li["qty"], 
                    li["rate"], 
                    li["amount"], 
                    li["product_id"], 
                    cid,
                    li.get("packing_multiplier", 1.0),
                    li["commission_amount"],
                    li.get("notes", None),
                    cid,
                )
            )
            
            if li["product_id"] != -1:
                cur_stock = conn.execute("SELECT stock_quantity FROM warehouse_inventory WHERE product_id = ? AND warehouse_id = ?", (li["product_id"], wid)).fetchone()
                old_stock = float(cur_stock["stock_quantity"] or 0) if cur_stock else 0
                qty_deduct = li["qty"] * li.get("packing_multiplier", 1.0)
                new_stock = old_stock - qty_deduct
                
                conn.execute(
                    """
                    INSERT INTO warehouse_inventory (product_id, warehouse_id, stock_quantity, company_id)
                    VALUES (?, ?, ?, ?)
                    ON CONFLICT(warehouse_id, product_id) DO UPDATE SET stock_quantity = COALESCE(warehouse_inventory.stock_quantity, 0) - ?
                    """,
                    (li["product_id"], wid, -qty_deduct, cid, qty_deduct)
                )
                
                conn.execute("""
                    INSERT INTO inventory_history (product_id, transaction_type, quantity_change, previous_stock, new_stock, reference, warehouse_id, company_id)
                    VALUES (?, 'OUT', ?, ?, ?, ?, ?, ?)
                """, (li["product_id"], -qty_deduct, old_stock, new_stock, f'Invoice #{invoice_number}', wid, cid))

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




# ── EXPENSES ────────────────────────────────────────────────────────────────

@app.route("/expenses")
@admin_required
def expenses():
    cid = current_user.company_id if hasattr(current_user, "company_id") and current_user.company_id else 1
    search      = request.args.get("search", "").strip()
    category    = request.args.get("category", "").strip()
    start_date  = request.args.get("start_date", "").strip()
    end_date    = request.args.get("end_date", "").strip()

    conn = get_connection()
    try:
        query  = """
            SELECT e.id, e.date, e.category, e.description, e.amount, e.created_at,
                   u.username as added_by_name
            FROM expenses e
            LEFT JOIN users u ON e.added_by = u.id
            WHERE e.company_id = ?
        """
        params = [cid]
        if search:
            query += " AND (e.description LIKE ? OR e.category LIKE ?)"
            params.extend([f"%{search}%", f"%{search}%"])
        if category:
            query += " AND e.category = ?"
            params.append(category)
        if start_date:
            query += " AND e.date >= ?"
            params.append(start_date)
        if end_date:
            query += " AND e.date <= ?"
            params.append(end_date)
        query += " ORDER BY e.date DESC, e.id DESC"

        rows = [dict(r) for r in conn.execute(query, params).fetchall()]
        total = sum(r["amount"] for r in rows)

        total_all_row = conn.execute("SELECT COALESCE(SUM(amount), 0), COUNT(*) FROM expenses WHERE company_id = ?", (cid,)).fetchone()
        total_all = total_all_row[0] if total_all_row else 0
        total_all_count = total_all_row[1] if total_all_row else 0

        # Current month spending
        current_month_prefix = date.today().strftime("%Y-%m")
        month_row = conn.execute(
            "SELECT COALESCE(SUM(amount), 0) FROM expenses WHERE date LIKE ? AND company_id = ?",
            (f"{current_month_prefix}%", cid)
        ).fetchone()
        this_month_total = month_row[0] if month_row else 0

        # Top category in filtered rows
        category_totals = {}
        for r in rows:
            cat = r.get("category") or "Uncategorized"
            category_totals[cat] = category_totals.get(cat, 0) + (r.get("amount") or 0)
        top_category = max(category_totals.items(), key=lambda x: x[1])[0] if category_totals else "—"

        # All distinct categories entered already in the DB
        categories = [r[0] for r in conn.execute(
            "SELECT DISTINCT category FROM expenses WHERE category IS NOT NULL AND category != '' AND company_id = ? ORDER BY category ASC",
            (cid,)
        ).fetchall()]
    finally:
        conn.close()

    return render_template(
        "expenses.html",
        expenses=rows,
        total=total,
        total_all=total_all,
        total_all_count=total_all_count,
        this_month_total=this_month_total,
        top_category=top_category,
        count=len(rows),
        categories=categories,
        filters={"search": search, "category": category,
                 "start_date": start_date, "end_date": end_date},
    )


@app.route("/expenses/add", methods=["POST"])
@admin_required
def expenses_add():
    cid = current_user.company_id if hasattr(current_user, "company_id") and current_user.company_id else 1
    date_val    = request.form.get("date", "").strip()
    category    = request.form.get("category", "").strip()
    description = request.form.get("description", "").strip()
    amount_str  = request.form.get("amount", "0").strip()
    try:
        amount = float(amount_str)
    except ValueError:
        flash("Invalid amount.", "danger")
        return redirect(url_for("expenses"))

    if not date_val or not category or amount <= 0:
        flash("Date, category and a positive amount are required.", "danger")
        return redirect(url_for("expenses"))

    conn = get_connection()
    try:
        conn.execute(
            "INSERT INTO expenses (date, category, description, amount, added_by, company_id) VALUES (?, ?, ?, ?, ?, ?)",
            (date_val, category, description, amount, current_user.id, cid),
        )
        conn.commit()
    finally:
        conn.close()
    flash("Expense added successfully.", "success")
    return redirect(url_for("expenses"))


@app.route("/expenses/edit/<int:expense_id>", methods=["POST"])
@admin_required
def expenses_edit(expense_id):
    cid = current_user.company_id if hasattr(current_user, "company_id") and current_user.company_id else 1
    date_val    = request.form.get("date", "").strip()
    category    = request.form.get("category", "").strip()
    description = request.form.get("description", "").strip()
    amount_str  = request.form.get("amount", "0").strip()
    try:
        amount = float(amount_str)
    except ValueError:
        flash("Invalid amount.", "danger")
        return redirect(url_for("expenses"))

    if not date_val or not category or amount <= 0:
        flash("Date, category and a positive amount are required.", "danger")
        return redirect(url_for("expenses"))

    conn = get_connection()
    try:
        cur = conn.execute("SELECT id FROM expenses WHERE id = ? AND company_id = ?", (expense_id, cid)).fetchone()
        if not cur:
            abort(404)
        conn.execute(
            "UPDATE expenses SET date=?, category=?, description=?, amount=? WHERE id=? AND company_id=?",
            (date_val, category, description, amount, expense_id, cid),
        )
        conn.commit()
    finally:
        conn.close()
    flash("Expense updated.", "success")
    return redirect(url_for("expenses"))


@app.route("/expenses/delete/<int:expense_id>", methods=["POST"])
@admin_required
def expenses_delete(expense_id):
    cid = current_user.company_id if hasattr(current_user, "company_id") and current_user.company_id else 1
    conn = get_connection()
    try:
        cur = conn.execute("SELECT id FROM expenses WHERE id = ? AND company_id = ?", (expense_id, cid)).fetchone()
        if not cur:
            abort(404)
        conn.execute("DELETE FROM expenses WHERE id=? AND company_id=?", (expense_id, cid))
        conn.commit()
    finally:
        conn.close()
    flash("Expense deleted.", "success")
    return redirect(url_for("expenses"))


@app.route("/purchases")
@login_required
def purchases():
    cid = current_user.company_id if hasattr(current_user, "company_id") and current_user.company_id else 1
    search = request.args.get('search', '').strip()
    supplier_id = request.args.get('supplier_id', '')
    product_id = request.args.get('product_id', '')
    start_date = request.args.get('start_date', '')
    end_date = request.args.get('end_date', '')
    
    conn = get_connection()
    try:
        query = '''
            SELECT p.id, p.reference_number, p.purchase_date, p.grand_total, p.amount_paid, p.remaining_amount, p.status, s.name as supplier_name, w.name as warehouse_name
            FROM purchases p
            LEFT JOIN suppliers s ON p.supplier_id = s.id
            LEFT JOIN warehouses w ON p.warehouse_id = w.id
            WHERE p.company_id = ?
        '''
        params = [cid]
        
        if search:
            query += ' AND (p.reference_number LIKE ? OR p.id LIKE ?)'
            params.extend(['%'+search+'%', '%'+search+'%'])
        
        if supplier_id:
            query += ' AND p.supplier_id = ?'
            params.append(supplier_id)
            
        if product_id:
            query += ' AND EXISTS (SELECT 1 FROM purchase_items pi WHERE pi.purchase_id = p.id AND pi.product_id = ? AND pi.company_id = ?)'
            params.extend([product_id, cid])
            
        if start_date:
            query += ' AND p.purchase_date >= ?'
            params.append(start_date)
            
        if end_date:
            query += ' AND p.purchase_date <= ?'
            params.append(end_date)
            
        query += ' ORDER BY p.purchase_date DESC, p.id DESC'
        
        cur = conn.execute(query, params)
        rows = [dict(r) for r in cur.fetchall()]
        
        if rows:
            purchase_ids = [str(r["id"]) for r in rows]
            items = conn.execute(f'''
                SELECT pi.purchase_id, pr.name as product_name, pi.qty 
                FROM purchase_items pi
                JOIN products pr ON pi.product_id = pr.id
                WHERE pi.purchase_id IN ({','.join(purchase_ids)}) AND pi.company_id = ?
            ''', (cid,)).fetchall()
            
            items_by_purchase = {}
            for item in items:
                pid = item["purchase_id"]
                if pid not in items_by_purchase:
                    items_by_purchase[pid] = []
                items_by_purchase[pid].append(dict(item))
                
            for r in rows:
                r["purchase_items"] = items_by_purchase.get(r["id"], [])
        
        suppliers = conn.execute('SELECT id, name FROM suppliers WHERE company_id = ? ORDER BY name ASC', (cid,)).fetchall()
        products = conn.execute('SELECT id, name FROM products WHERE company_id = ? ORDER BY name ASC', (cid,)).fetchall()
    finally:
        conn.close()
    return render_template("purchases.html", purchases=rows, suppliers=suppliers, products=products, filters={'search': search, 'supplier_id': supplier_id, 'product_id': product_id, 'start_date': start_date, 'end_date': end_date})

@app.route("/purchases/new", methods=["GET"])
@admin_required
def new_purchase():
    cid = current_user.company_id if hasattr(current_user, "company_id") and current_user.company_id else 1
    conn = get_connection()
    try:
        suppliers = [dict(row) for row in conn.execute("SELECT id, name FROM suppliers WHERE company_id = ? ORDER BY name ASC", (cid,)).fetchall()]
        products = [dict(row) for row in conn.execute("SELECT id, name, cost_price, unit FROM products WHERE company_id = ? ORDER BY name ASC", (cid,)).fetchall()]
        warehouses = [dict(row) for row in conn.execute("SELECT id, name FROM warehouses WHERE company_id = ? ORDER BY name ASC", (cid,)).fetchall()]
    finally:
        conn.close()
    return render_template("purchase_new.html", suppliers=suppliers, products=products, warehouses=warehouses, purchase=None)

@app.route("/purchases/edit/<int:purchase_id>", methods=["GET"])
@admin_required
def edit_purchase(purchase_id):
    cid = current_user.company_id if hasattr(current_user, "company_id") and current_user.company_id else 1
    conn = get_connection()
    try:
        purchase = conn.execute("SELECT * FROM purchases WHERE id = ? AND company_id = ?", (purchase_id, cid)).fetchone()
        if not purchase:
            abort(404)
        
        purchase = dict(purchase)
        
        items = conn.execute('''
            SELECT pi.product_id, pi.qty, pi.cost_price, p.name 
            FROM purchase_items pi
            JOIN products p ON p.id = pi.product_id
            WHERE pi.purchase_id = ? AND pi.company_id = ?
        ''', (purchase_id, cid)).fetchall()
        purchase['items'] = [dict(i) for i in items]
        
        suppliers = [dict(row) for row in conn.execute("SELECT id, name FROM suppliers WHERE company_id = ? ORDER BY name ASC", (cid,)).fetchall()]
        products = [dict(row) for row in conn.execute("SELECT id, name, cost_price, unit FROM products WHERE company_id = ? ORDER BY name ASC", (cid,)).fetchall()]
        warehouses = [dict(row) for row in conn.execute("SELECT id, name FROM warehouses WHERE company_id = ? ORDER BY name ASC", (cid,)).fetchall()]
    finally:
        conn.close()
    return render_template("purchase_new.html", suppliers=suppliers, products=products, purchase=purchase, warehouses=warehouses)

@app.route("/purchases/new", methods=["POST"])
@admin_required
def create_purchase():
    cid = current_user.company_id if hasattr(current_user, "company_id") and current_user.company_id else 1
    data = request.json
    supplier_id = data.get("supplier_id")
    purchase_date = data.get("purchase_date")
    reference_number = data.get("reference_number", "")
    items = data.get("items", [])
    payment_amount = float(data.get("payment_amount", 0))
    payment_method = data.get("payment_method", "cash")
    other_charges = float(data.get("other_charges", 0))
    wid_raw = data.get("warehouse_id")
    wid = int(wid_raw) if wid_raw else (current_user.warehouse_id or 1)

    if not supplier_id or not items:
        return jsonify({"ok": False, "error": "Missing supplier or items"}), 400

    conn = get_connection()
    try:
        # Validate supplier belongs to company
        supp_check = conn.execute("SELECT id FROM suppliers WHERE id = ? AND company_id = ?", (supplier_id, cid)).fetchone()
        if not supp_check:
            return jsonify({"ok": False, "error": "Invalid or unauthorized supplier."}), 400

        # Validate warehouse belongs to company
        wh_check = conn.execute("SELECT id FROM warehouses WHERE id = ? AND company_id = ?", (wid, cid)).fetchone()
        if not wh_check:
            return jsonify({"ok": False, "error": "Invalid or unauthorized warehouse."}), 400

        # Validate all products belong to company
        for item in items:
            pid = int(item.get("product_id", 0))
            p_check = conn.execute("SELECT id FROM products WHERE id = ? AND company_id = ?", (pid, cid)).fetchone()
            if not p_check:
                return jsonify({"ok": False, "error": f"Invalid or unauthorized product ID {pid}."}), 400

        conn.execute("BEGIN")
        
        subtotal = sum(float(item.get("qty", 0)) * float(item.get("cost_price", 0)) for item in items)
        grand_total = subtotal + other_charges
        amount_paid = payment_amount
        remaining_amount = grand_total - amount_paid
        
        status = 'unpaid'
        if abs(remaining_amount) < 0.001 or amount_paid >= grand_total:
            status = 'paid'
            remaining_amount = 0
        elif amount_paid > 0:
            status = 'partial'

        cur = conn.execute('''
            INSERT INTO purchases (supplier_id, reference_number, purchase_date, subtotal, other_charges, grand_total, amount_paid, remaining_amount, status, warehouse_id, company_id)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (supplier_id, reference_number, purchase_date, subtotal, other_charges, grand_total, amount_paid, remaining_amount, status, wid, cid))
        
        purchase_id = cur.lastrowid
        
        if amount_paid > 0:
            conn.execute('''
                INSERT INTO supplier_payments (supplier_id, purchase_id, amount, payment_date, payment_method, company_id)
                VALUES (?, ?, ?, ?, ?, ?)
            ''', (supplier_id, purchase_id, amount_paid, purchase_date, payment_method, cid))

        for item in items:
            qty = round(float(item["qty"]), 4)
            cost = float(item["cost_price"])
            pid = int(item["product_id"])
            amount = round(qty * cost, 2)
            
            conn.execute('''
                INSERT INTO purchase_items (purchase_id, product_id, qty, cost_price, amount, company_id)
                VALUES (?, ?, ?, ?, ?, ?)
            ''', (purchase_id, pid, qty, cost, amount, cid))
            
            # Update inventory
            cur = conn.execute("SELECT stock_quantity FROM warehouse_inventory WHERE product_id = ? AND warehouse_id = ? AND company_id = ?", (pid, wid, cid))
            row = cur.fetchone()
            old_stock = float(row["stock_quantity"] or 0) if row else 0
            new_stock = round(old_stock + qty, 4)
            
            conn.execute('''
                INSERT INTO warehouse_inventory (product_id, warehouse_id, stock_quantity, company_id)
                VALUES (?, ?, ?, ?)
                ON CONFLICT(warehouse_id, product_id) DO UPDATE SET stock_quantity = ?
            ''', (pid, wid, new_stock, cid, new_stock))
            
            conn.execute('''
                INSERT INTO inventory_history (product_id, transaction_type, quantity_change, previous_stock, new_stock, reference, supplier_id, warehouse_id, company_id)
                VALUES (?, 'IN', ?, ?, ?, ?, ?, ?, ?)
            ''', (pid, qty, old_stock, new_stock, f"Purchase #{purchase_id}", supplier_id, wid, cid))

        conn.commit()
        return jsonify({"ok": True, "purchase_id": purchase_id})
    except Exception as e:
        conn.rollback()
        return jsonify({"ok": False, "error": str(e)}), 500
    finally:
        conn.close()

@app.route("/api/purchases/<int:purchase_id>", methods=["POST"])
@admin_required
def update_purchase(purchase_id):
    cid = current_user.company_id if hasattr(current_user, "company_id") and current_user.company_id else 1
    data = request.json
    supplier_id = data.get("supplier_id")
    purchase_date = data.get("purchase_date")
    reference_number = data.get("reference_number", "")
    items = data.get("items", [])
    other_charges = float(data.get("other_charges", 0))
    force = data.get("force", False)

    if not supplier_id or not items:
        return jsonify({"ok": False, "error": "Missing supplier or items"}), 400

    conn = get_connection()
    try:
        # Verify purchase belongs to tenant
        old_purch = conn.execute("SELECT supplier_id, warehouse_id, amount_paid FROM purchases WHERE id = ? AND company_id = ?", (purchase_id, cid)).fetchone()
        if not old_purch:
            return jsonify({"ok": False, "error": "Purchase not found"}), 404

        # Validate supplier belongs to company
        supp_check = conn.execute("SELECT id FROM suppliers WHERE id = ? AND company_id = ?", (supplier_id, cid)).fetchone()
        if not supp_check:
            return jsonify({"ok": False, "error": "Invalid or unauthorized supplier."}), 400

        # Determine warehouse_id
        wid_raw = data.get("warehouse_id")
        if wid_raw:
            wid = int(wid_raw)
        else:
            wid = int(old_purch["warehouse_id"]) if old_purch["warehouse_id"] else (current_user.warehouse_id or 1)

        wh_check = conn.execute("SELECT id FROM warehouses WHERE id = ? AND company_id = ?", (wid, cid)).fetchone()
        if not wh_check:
            return jsonify({"ok": False, "error": "Invalid or unauthorized warehouse."}), 400

        conn.execute("BEGIN")

        # 1. Fetch old items to calculate net stock changes
        old_items_db = conn.execute("SELECT product_id, qty FROM purchase_items WHERE purchase_id = ? AND company_id = ?", (purchase_id, cid)).fetchall()
        old_items = {}
        for row in old_items_db:
            pid = str(row["product_id"])
            old_items[pid] = round(old_items.get(pid, 0) + float(row["qty"] or 0), 4)
            
        new_items = {}
        for item in items:
            pid = str(item["product_id"])
            new_items[pid] = round(new_items.get(pid, 0) + float(item.get("qty", 0)), 4)
            
        # 2. Check for negative inventory
        warnings = []
        for pid in set(old_items.keys()).union(new_items.keys()):
            old_qty = old_items.get(pid, 0)
            new_qty = new_items.get(pid, 0)
            diff = round(new_qty - old_qty, 4)
            
            if diff < -1e-5:
                cur_stock = conn.execute("SELECT stock_quantity FROM warehouse_inventory WHERE product_id = ? AND warehouse_id = ? AND company_id = ?", (pid, wid, cid)).fetchone()
                current_stock = float(cur_stock["stock_quantity"] or 0) if cur_stock else 0
                projected_stock = round(current_stock + diff, 4)
                if projected_stock < -1e-5:
                    p_name = conn.execute("SELECT name FROM products WHERE id = ? AND company_id = ?", (pid, cid)).fetchone()["name"]
                    warnings.append(f"{p_name} will drop to {projected_stock} stock.")
                        
        if warnings and not force:
            conn.rollback()
            return jsonify({
                "ok": False, 
                "requires_confirmation": True, 
                "message": "Updating this purchase will cause negative inventory:\n" + "\n".join(warnings) + "\n\nAre you sure you want to proceed?"
            })
            
        # 3. Apply net changes to products
        for pid in set(old_items.keys()).union(new_items.keys()):
            old_qty = old_items.get(pid, 0)
            new_qty = new_items.get(pid, 0)
            diff = round(new_qty - old_qty, 4)
            
            if abs(diff) > 1e-5:
                cur_stock = conn.execute("SELECT stock_quantity FROM warehouse_inventory WHERE product_id = ? AND warehouse_id = ? AND company_id = ?", (pid, wid, cid)).fetchone()
                current_stock = float(cur_stock["stock_quantity"] or 0) if cur_stock else 0
                new_stock = round(current_stock + diff, 4)
                
                conn.execute('''
                    INSERT INTO warehouse_inventory (product_id, warehouse_id, stock_quantity, company_id)
                    VALUES (?, ?, ?, ?)
                    ON CONFLICT(warehouse_id, product_id) DO UPDATE SET stock_quantity = ?
                ''', (pid, wid, new_stock, cid, new_stock))
                
                # Log to history
                trans_type = 'IN' if diff > 0 else 'OUT'
                conn.execute('''
                    INSERT INTO inventory_history (product_id, transaction_type, quantity_change, previous_stock, new_stock, reference, supplier_id, warehouse_id, company_id)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                ''', (pid, trans_type, abs(diff), current_stock, new_stock, f"Edit Purchase #{purchase_id}", supplier_id, wid, cid))
                    
        # 4. Delete old items and insert new
        conn.execute("DELETE FROM purchase_items WHERE purchase_id = ? AND company_id = ?", (purchase_id, cid))
        
        subtotal = 0
        for item in items:
            qty = round(float(item["qty"]), 4)
            cost = float(item["cost_price"])
            pid = int(item["product_id"])
            amount = round(qty * cost, 2)
            subtotal += amount
            
            conn.execute('''
                INSERT INTO purchase_items (purchase_id, product_id, qty, cost_price, amount, company_id)
                VALUES (?, ?, ?, ?, ?, ?)
            ''', (purchase_id, pid, qty, cost, amount, cid))
            
        # 5. Update purchase master record
        grand_total = subtotal + other_charges
        amount_paid = float(old_purch["amount_paid"] or 0)
        remaining_amount = grand_total - amount_paid
        
        status = 'unpaid'
        if abs(remaining_amount) < 0.001 or amount_paid >= grand_total:
            status = 'paid'
            remaining_amount = 0
        elif amount_paid > 0:
            status = 'partial'
            
        conn.execute('''
            UPDATE purchases
            SET supplier_id = ?, purchase_date = ?, reference_number = ?, subtotal = ?, other_charges = ?, grand_total = ?, remaining_amount = ?, status = ?, warehouse_id = ?
            WHERE id = ? AND company_id = ?
        ''', (supplier_id, purchase_date, reference_number, subtotal, other_charges, grand_total, remaining_amount, status, wid, purchase_id, cid))
        
        conn.commit()
        return jsonify({"ok": True, "purchase_id": purchase_id})
    except Exception as e:
        conn.rollback()
        return jsonify({"ok": False, "error": str(e)}), 500
    finally:
        conn.close()

@app.route("/api/purchases/<int:purchase_id>/delete", methods=["POST"])
@admin_required
def delete_purchase(purchase_id):
    cid = current_user.company_id if hasattr(current_user, "company_id") and current_user.company_id else 1
    data = request.json or {}
    force = data.get("force", False)
    
    conn = get_connection()
    try:
        conn.execute("BEGIN")
        
        purchase = conn.execute("SELECT supplier_id, warehouse_id FROM purchases WHERE id = ? AND company_id = ?", (purchase_id, cid)).fetchone()
        if not purchase:
            conn.execute("ROLLBACK")
            return jsonify({"ok": False, "error": "Purchase not found"}), 404
        supplier_id = purchase["supplier_id"]
        wid = purchase["warehouse_id"] or 1
            
        items = conn.execute("SELECT product_id, qty FROM purchase_items WHERE purchase_id = ? AND company_id = ?", (purchase_id, cid)).fetchall()
        
        # 1. Check for negative inventory
        warnings = []
        for item in items:
            pid = item["product_id"]
            qty = round(float(item["qty"]), 4)
            
            cur_stock = conn.execute("SELECT stock_quantity FROM warehouse_inventory WHERE product_id = ? AND warehouse_id = ? AND company_id = ?", (pid, wid, cid)).fetchone()
            current_stock = float(cur_stock["stock_quantity"] or 0) if cur_stock else 0
            projected_stock = round(current_stock - qty, 4)
            if projected_stock < -1e-5:
                p_name = conn.execute("SELECT name FROM products WHERE id = ? AND company_id = ?", (pid, cid)).fetchone()["name"]
                warnings.append(f"{p_name} will drop to {projected_stock} stock.")
                    
        if warnings and not force:
            conn.rollback()
            return jsonify({
                "ok": False, 
                "requires_confirmation": True, 
                "message": "Deleting this purchase will cause negative inventory:\n" + "\n".join(warnings) + "\n\nAre you sure you want to proceed?"
            })
            
        # 2. Revert inventory
        for item in items:
            pid = item["product_id"]
            qty = round(float(item["qty"]), 4)
            
            cur_stock = conn.execute("SELECT stock_quantity FROM warehouse_inventory WHERE product_id = ? AND warehouse_id = ? AND company_id = ?", (pid, wid, cid)).fetchone()
            current_stock = float(cur_stock["stock_quantity"] or 0) if cur_stock else 0
            new_stock = round(current_stock - qty, 4)
            
            conn.execute('''
                INSERT INTO warehouse_inventory (product_id, warehouse_id, stock_quantity, company_id)
                VALUES (?, ?, ?, ?)
                ON CONFLICT(warehouse_id, product_id) DO UPDATE SET stock_quantity = ?
            ''', (pid, wid, new_stock, cid, new_stock))
            
            conn.execute('''
                INSERT INTO inventory_history (product_id, transaction_type, quantity_change, previous_stock, new_stock, reference, supplier_id, warehouse_id, company_id)
                VALUES (?, 'OUT', ?, ?, ?, ?, ?, ?, ?)
            ''', (pid, qty, current_stock, new_stock, f"Delete Purchase #{purchase_id}", supplier_id, wid, cid))
                
        # 3. Delete records
        conn.execute("DELETE FROM supplier_payments WHERE purchase_id = ? AND company_id = ?", (purchase_id, cid))
        conn.execute("DELETE FROM purchase_items WHERE purchase_id = ? AND company_id = ?", (purchase_id, cid))
        conn.execute("DELETE FROM purchases WHERE id = ? AND company_id = ?", (purchase_id, cid))
        
        conn.commit()
        return jsonify({"ok": True})
    except Exception as e:
        conn.rollback()
        return jsonify({"ok": False, "error": str(e)}), 500
    finally:
        conn.close()


@app.route("/purchases/<int:purchase_id>")
@login_required
def purchase_detail(purchase_id):
    cid = current_user.company_id if hasattr(current_user, "company_id") and current_user.company_id else 1
    conn = get_connection()
    try:
        purchase = conn.execute('''
            SELECT p.*, s.name as supplier_name 
            FROM purchases p 
            LEFT JOIN suppliers s ON p.supplier_id = s.id 
            WHERE p.id = ? AND p.company_id = ?
        ''', (purchase_id, cid)).fetchone()
        
        if not purchase:
            abort(404)

        items = conn.execute('''
            SELECT pi.*, pr.name as product_name
            FROM purchase_items pi
            LEFT JOIN products pr ON pi.product_id = pr.id
            WHERE pi.purchase_id = ? AND pi.company_id = ?
        ''', (purchase_id, cid)).fetchall()
        
        payments = conn.execute('''
            SELECT * FROM supplier_payments WHERE purchase_id = ? AND company_id = ? ORDER BY payment_date DESC, id DESC
        ''', (purchase_id, cid)).fetchall()
    finally:
        conn.close()
        
    return render_template("purchase_detail.html", purchase=purchase, items=items, payments=payments)

@app.route("/api/supplier_payments", methods=["POST"])
@admin_required
def add_supplier_payment():
    cid = current_user.company_id if hasattr(current_user, "company_id") and current_user.company_id else 1
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
        # Validate supplier belongs to company
        supp = conn.execute("SELECT id FROM suppliers WHERE id = ? AND company_id = ?", (supplier_id, cid)).fetchone()
        if not supp:
            return jsonify({"ok": False, "error": "Invalid supplier."}), 400

        conn.execute("BEGIN")
        conn.execute('''
            INSERT INTO supplier_payments (supplier_id, purchase_id, amount, payment_date, payment_method, notes, company_id)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        ''', (supplier_id, purchase_id, amount, payment_date, payment_method, notes, cid))
        
        if purchase_id:
            cur = conn.execute("SELECT grand_total, amount_paid FROM purchases WHERE id = ? AND company_id = ?", (purchase_id, cid))
            purchase = cur.fetchone()
            if purchase:
                curr_paid = float(purchase["amount_paid"] or 0)
                curr_total = float(purchase["grand_total"] or 0)
                new_paid = curr_paid + amount
                new_remaining = curr_total - new_paid
                status = 'unpaid'
                if abs(new_remaining) < 0.001 or new_paid >= curr_total:
                    status = 'paid'
                    new_remaining = 0
                elif new_paid > 0:
                    status = 'partial'
                
                conn.execute('''
                    UPDATE purchases SET amount_paid = ?, remaining_amount = ?, status = ? WHERE id = ? AND company_id = ?
                ''', (new_paid, new_remaining, status, purchase_id, cid))
            else:
                conn.rollback()
                return jsonify({"ok": False, "error": "Invalid purchase."}), 400
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
