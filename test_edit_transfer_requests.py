import requests
import sqlite3

session = requests.Session()

def get_product_stock(product_id, warehouse_id):
    conn = sqlite3.connect('database.db')
    cur = conn.cursor()
    cur.execute("SELECT stock_quantity FROM warehouse_inventory WHERE product_id = ? AND warehouse_id = ?", (product_id, warehouse_id))
    row = cur.fetchone()
    conn.close()
    return float(row[0]) if row else 0.0

print("1. Logging in as admin...")
login_res = session.post("http://127.0.0.1:5000/login", data={"username": "admin", "password": "admin"})

# Inject stock so we can transfer
conn = sqlite3.connect('database.db')
conn.execute("INSERT INTO warehouse_inventory (product_id, warehouse_id, stock_quantity) VALUES (1, 1, 100) ON CONFLICT(warehouse_id, product_id) DO UPDATE SET stock_quantity = 100")
conn.commit()
conn.close()

print("2. Checking initial inventory...")
initial_source = get_product_stock(1, 1)
initial_dest = get_product_stock(1, 2)
print(f"   Source (Main): {initial_source}, Dest (LA): {initial_dest}")

print("3. Creating a new transfer...")
transfer_payload = {
    "source_warehouse_id": "1",
    "destination_warehouse_id": "2",
    "notes": "Test Transfer",
    "items": [
        {"product_id": "1", "quantity": "5"}
    ]
}
res = session.post("http://127.0.0.1:5000/inventory/transfer", json=transfer_payload)
print(res.text)

print("4. Verifying stock after create...")
mid_source = get_product_stock(1, 1)
mid_dest = get_product_stock(1, 2)
print(f"   Source (Main): {mid_source}, Dest (LA): {mid_dest}")
assert mid_source == initial_source - 5
assert mid_dest == initial_dest + 5

# get the transfer ID
conn = sqlite3.connect('database.db')
transfer_id = conn.execute("SELECT id FROM inventory_transfers ORDER BY id DESC LIMIT 1").fetchone()[0]
conn.close()

print(f"5. Editing transfer #{transfer_id}...")
edit_payload = {
    "source_warehouse_id": "1",
    "destination_warehouse_id": "2",
    "notes": "Test Transfer Edited",
    "items": [
        {"product_id": "1", "quantity": "7"} # increase by 2
    ]
}
res = session.post(f"http://127.0.0.1:5000/inventory/transfer/edit/{transfer_id}", json=edit_payload)
print(res.text)

print("6. Verifying stock after edit...")
final_source = get_product_stock(1, 1)
final_dest = get_product_stock(1, 2)
print(f"   Final Source (Main): {final_source}, Final Dest (LA): {final_dest}")
assert final_source == initial_source - 7
assert final_dest == initial_dest + 7

print("Success! Transfer created and edited correctly!")
