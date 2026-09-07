import sqlite3
from collections import defaultdict
import json

DB_PATH = 'database.db'

def find_duplicates():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()

    # Get all sales and their items
    # We will use GROUP_CONCAT or just fetch them all and group in Python.
    # Grouping in Python is easier for exact set matching.

    # 1. Fetch all sale items with product names
    items_cur = cur.execute('''
        SELECT 
            si.sale_id,
            si.product_id,
            p.name as product_name,
            si.qty
        FROM sale_items si
        JOIN products p ON si.product_id = p.id
    ''')
    
    sale_items_map = defaultdict(list)
    for row in items_cur.fetchall():
        # Store tuple of (product_name, qty) for each sale
        # We use product_name instead of id in case products were recreated, but id is fine too.
        # Let's use product_id and product_name for display
        sale_items_map[row['sale_id']].append({
            'product_id': row['product_id'],
            'product_name': row['product_name'],
            'qty': row['qty']
        })

    # 2. Fetch all sales with customer info
    sales_cur = cur.execute('''
        SELECT 
            s.id,
            s.invoice_number,
            s.invoice_date,
            s.customer_id,
            c.name as customer_name,
            s.grand_total
        FROM sales s
        JOIN customers c ON s.customer_id = c.id
    ''')

    # Grouping structure:
    # key: (customer_id, tuple_of_sorted_items_by_id_and_qty)
    # value: list of sales
    grouped_sales = defaultdict(list)

    for row in sales_cur.fetchall():
        sale_id = row['id']
        items = sale_items_map.get(sale_id, [])
        
        # Sort items by product_id so the tuple is consistent regardless of insertion order
        items.sort(key=lambda x: x['product_id'])
        
        # Create a hashable tuple representing the exact items and quantities
        items_tuple = tuple((item['product_id'], item['qty']) for item in items)
        
        # The unique signature for a sale
        signature = (row['customer_id'], items_tuple)
        
        sale_data = {
            'invoice_number': row['invoice_number'],
            'invoice_date': row['invoice_date'],
            'customer_name': row['customer_name'],
            'grand_total': row['grand_total'],
            'items_display': [(item['product_name'], item['qty']) for item in items]
        }
        
        grouped_sales[signature].append(sale_data)

    # 3. Filter and print duplicates
    duplicates_found = False
    for signature, sales_list in grouped_sales.items():
        if len(sales_list) > 1:
            duplicates_found = True
            customer_name = sales_list[0]['customer_name']
            items_display = sales_list[0]['items_display']
            
            print("="*60)
            print(f"DUPLICATE FOUND FOR CUSTOMER: {customer_name}")
            print("Matching Items:")
            for item_name, qty in items_display:
                print(f"  - {item_name} (Qty: {qty})")
            
            print("\nInvoices with these exact items:")
            for sale in sales_list:
                print(f"  > Invoice: {sale['invoice_number']} | Date: {sale['invoice_date']} | Total: ${sale['grand_total']}")
            print("="*60)
            print()

    if not duplicates_found:
        print("No duplicate sales found matching the criteria (same customer, same products & quantities).")

if __name__ == "__main__":
    find_duplicates()
