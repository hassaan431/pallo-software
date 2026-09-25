from flask import Blueprint, render_template, abort, request, make_response, current_app
from database import get_public_products
from xhtml2pdf import pisa
from io import BytesIO
import os

public_bp = Blueprint('public_bp', __name__)

def fetch_resources(uri, rel):
    """Callback to resolve local paths for xhtml2pdf"""
    if uri.startswith('/static/'):
        path = os.path.join(current_app.root_path, uri.lstrip('/'))
        return path
    return uri

from flask_login import current_user
from flask import redirect, url_for

@public_bp.route('/')
def home():
    if current_user.is_authenticated:
        if current_user.role == 'admin':
            return redirect(url_for('dashboard'))
        elif current_user.role == 'salesman':
            return redirect(url_for('sales'))
    
    return redirect(url_for('login'))

@public_bp.route('/products')
def catalog():
    brand_filter = request.args.get('brand')
    products = get_public_products()
    
    brands_set = set()
    for p in products:
        if p.get('brand'):
            brands_set.add(p['brand'])
    all_brands = sorted(list(brands_set))
    
    if brand_filter:
        products = [p for p in products if p.get('brand') == brand_filter]
        
    return render_template('public_catalog.html', products=products, selected_brand=brand_filter, all_brands=all_brands)

@public_bp.route('/about')
def about():
    return render_template('public_about.html')

@public_bp.route('/brands')
def brands():
    products = get_public_products()
    brands_set = set()
    for p in products:
        if p.get('brand'):
            brands_set.add(p['brand'])
    unique_brands = sorted(list(brands_set))
    return render_template('public_brands.html', brands=unique_brands)

from flask import send_from_directory

@public_bp.route('/brochure/download')
def download_brochure():
    downloads_dir = os.path.join(current_app.root_path, 'static', 'downloads')
    filename = 'brochure.pdf'
    file_path = os.path.join(downloads_dir, filename)
    
    if not os.path.exists(file_path):
        return "Brochure is not currently available. Please check back later.", 404
        
    return send_from_directory(downloads_dir, filename, as_attachment=True, download_name="AK_Distributors_Brochure.pdf")
