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

@public_bp.route('/')
def home():
    # Fetch unique brands for the homepage
    products = get_public_products()
    brands_set = set()
    for p in products:
        if p.get('brand'):
            brands_set.add(p['brand'])
    unique_brands = sorted(list(brands_set))
    
    # Optional: Just take the first 8 brands for the homepage, or pass all
    featured_brands = unique_brands[:8]
    
    return render_template('public_home.html', featured_brands=featured_brands)

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

@public_bp.route('/brochure/download')
def download_brochure():
    products = get_public_products()
    
    # Group by brand
    brands = {}
    brand_logos = {}
    from database import get_brand_logo_filename
    for p in products:
        b = p.get('brand') or 'Other'
        if b not in brands:
            brands[b] = []
            logo_name = get_brand_logo_filename(b)
            brand_logos[b] = logo_name if logo_name else False
        brands[b].append(p)
        
    # Render HTML template
    html = render_template('brochure.html', brands=brands, brand_logos=brand_logos)
    
    # Create PDF
    pdf_file = BytesIO()
    pisa_status = pisa.CreatePDF(
        html, 
        dest=pdf_file, 
        link_callback=fetch_resources
    )
    
    if pisa_status.err:
        return "Error generating PDF", 500
        
    response = make_response(pdf_file.getvalue())
    response.headers['Content-Type'] = 'application/pdf'
    response.headers['Content-Disposition'] = 'attachment; filename="AK_Distributors_Brochure.pdf"'
    
    return response

