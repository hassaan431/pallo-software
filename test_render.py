from app import app
from flask import render_template

with app.test_request_context():
    try:
        render_template("dashboard.html", 
            monthly_profit=100.0,
            monthly_margin=10.0,
            daily_revenue=50.0,
            daily_profit=20.0,
            monthly_revenue=500.0,
            recent_sales=[{"invoice_number": "INV-1", "customer_name": "Test", "invoice_date": "2026-08-12", "grand_total": 50.0, "profit_margin": 10.0, "profit_amount": 5.0, "payment_type": "cash", "status": "paid", "id": 1}],
            upcoming_payments=[],
            daily_sales_labels=[],
            daily_sales_data=[]
        )
        print("Template rendered successfully.")
    except Exception as e:
        import traceback
        traceback.print_exc()
