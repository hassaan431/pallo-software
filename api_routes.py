from flask import Blueprint, jsonify
from database import get_public_products

api_bp = Blueprint('api_bp', __name__)

@api_bp.route('/public/products', methods=['GET'])
def get_products():
    try:
        products = get_public_products()
        return jsonify({
            'success': True,
            'data': products
        })
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@api_bp.route('/public/brands', methods=['GET'])
def get_brands():
    try:
        products = get_public_products()
        brands_set = set()
        for p in products:
            if p.get('brand'):
                brands_set.add(p['brand'])
        
        unique_brands = sorted(list(brands_set))
        
        # We could optionally get brand logos here if needed
        from database import get_brand_logo_filename
        brand_data = []
        for brand in unique_brands:
            logo = get_brand_logo_filename(brand)
            brand_data.append({
                'name': brand,
                'logo_url': f"/static/logos/brands/{logo}" if logo else None
            })
            
        return jsonify({
            'success': True,
            'data': brand_data
        })
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500
