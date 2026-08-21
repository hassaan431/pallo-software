from flask import Blueprint, redirect, url_for
from flask_login import current_user

public_bp = Blueprint('public_bp', __name__)

@public_bp.route('/')
@public_bp.route('/products')
@public_bp.route('/about')
@public_bp.route('/brands')
@public_bp.route('/brochure/download')
def redirect_to_app():
    if current_user.is_authenticated:
        if getattr(current_user, 'role', 'admin') == 'salesman':
            return redirect(url_for('pos'))
        return redirect(url_for('dashboard'))
    return redirect(url_for('login'))
