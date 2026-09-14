import sqlite3
import json
from flask import Flask, request
from app import app, get_connection

with app.test_request_context('/sales/edit/999', method='POST', data={
    'invoice_number': 'Q-999',
    'customer_id': '1',
    'invoice_date': '2026-09-12',
    'items': json.dumps([{"product_id":999,"description":"Test","qty":5,"rate":2,"amount":10,"packing_multiplier":1,"print_dual_units":0}]),
    'subtotal': '10',
    'discount_amount': '0',
    'grand_total': '10',
    'payment_type': 'cash',
    'warehouse_id': '1',
    'salesman_id': '1'
}):
    # Mock current_user
    from flask_login import login_user
    class DummyUser:
        is_authenticated = True
        id = 1
        warehouse_id = 1
        is_active = True
        def get_id(self): return "1"
    
    # We can't easily mock login_user in a script without app context full setup, 
    # Let's just bypass by testing the function logic directly, or just hit the db
    pass

