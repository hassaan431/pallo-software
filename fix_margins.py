import sqlite3
import os

def fix_margins(db_path='database.db'):
    if not os.path.exists(db_path):
        print(f"Error: {db_path} not found.")
        return
        
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()

    # 1. Fix cost_price bug from POS
    # In POS, cost_price was accidentally set to the product_id.
    # We will update cost_price to the current products.cost_price for ALL sale_items
    # where the cost_price looks like it might be the product_id (or just all of them to be safe, 
    # since we want to fix margins anyway).
    print("Fixing cost_price for all sale items...")
    cur.execute("""
        UPDATE sale_items 
        SET cost_price = (SELECT cost_price FROM products WHERE id = sale_items.product_id)
        WHERE product_id IS NOT NULL
    """)
    print(f"Updated {cur.rowcount} sale items with correct current cost_price.")

    # 2. Fix packing_multiplier for OLD open product sales
    # If packing_multiplier is 1.0, but the product is an open product, and the rate charged
    # is significantly less than the selling_price of the full product, we can infer the packing multiplier.
    print("Fixing packing_multiplier for open products...")
    cur.execute("""
        SELECT si.id, si.rate, si.packing_multiplier, p.selling_price, p.name 
        FROM sale_items si
        JOIN products p ON p.id = si.product_id
        WHERE p.is_open = 1 AND si.packing_multiplier = 1.0 AND p.selling_price > 0
    """)
    open_sales = cur.fetchall()
    
    updated_pm = 0
    for sale in open_sales:
        rate = float(sale['rate'] or 0)
        selling_price = float(sale['selling_price'] or 0)
        
        if rate > 0 and selling_price > 0 and rate < selling_price:
            # Infer packing multiplier
            inferred_pm = rate / selling_price
            
            # Round to sensible fractions like 0.5, 0.25, etc. if it's close.
            # But just storing it accurately up to 3 decimals is safer.
            inferred_pm = round(inferred_pm, 3)
            
            # Only update if the margin difference is massive (e.g inferred_pm < 0.9)
            if inferred_pm < 0.9:
                cur.execute("""
                    UPDATE sale_items
                    SET packing_multiplier = ?
                    WHERE id = ?
                """, (inferred_pm, sale['id']))
                updated_pm += 1

    print(f"Fixed packing_multiplier for {updated_pm} open product sale items.")
    
    conn.commit()
    conn.close()
    print("Margin fixes complete! Please check your reports.")

if __name__ == '__main__':
    fix_margins()
