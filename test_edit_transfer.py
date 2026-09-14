import asyncio
import sqlite3
from playwright.async_api import async_playwright

def get_product_stock(product_id, warehouse_id):
    conn = sqlite3.connect('database.db')
    cur = conn.cursor()
    cur.execute("SELECT stock_quantity FROM warehouse_inventory WHERE product_id = ? AND warehouse_id = ?", (product_id, warehouse_id))
    row = cur.fetchone()
    conn.close()
    return float(row[0]) if row else 0.0

async def main():
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page()
        
        print("1. Navigating to login page...")
        await page.goto("http://127.0.0.1:5000/login")
        
        print("2. Logging in as admin...")
        await page.fill("input[name='username']", "admin")
        await page.fill("input[name='password']", "admin")
        await page.click("button[type='submit']")
        
        # Wait for login to complete (should redirect to dashboard)
        await page.wait_for_url("http://127.0.0.1:5000/")
        
        print("3. Navigating to Inventory Transfers...")
        await page.goto("http://127.0.0.1:5000/inventory/transfers")
        
        print("4. Checking for existing transfers...")
        await page.wait_for_load_state("networkidle")
        edit_buttons = await page.query_selector_all("a:has-text('Edit')")
        
        if not edit_buttons:
            print("   No transfers found. Creating a new transfer...")
            await page.click("a:has-text('New Transfer')")
            await page.wait_for_selector("h2:has-text('Transfer Inventory')")
            
            # Add some initial stock directly to DB to ensure transfer works
            conn = sqlite3.connect('database.db')
            conn.execute("INSERT INTO warehouse_inventory (product_id, warehouse_id, stock_quantity) VALUES (1, 1, 100) ON CONFLICT(warehouse_id, product_id) DO UPDATE SET stock_quantity = 100")
            conn.commit()
            conn.close()

            # Select Main Warehouse as source
            await page.select_option("#source_warehouse_id", "1")
            
            # Select LA Warehouse as destination
            await page.select_option("#destination_warehouse_id", "2")
            
            # Wait for products to load
            await page.wait_for_timeout(1000)
            
            # Fill out the first product
            selects = await page.query_selector_all(".prod-select")
            await page.evaluate(f"(el) => el.tomselect.setValue('1')", selects[0])
            
            qty_inputs = await page.query_selector_all(".qty-input")
            await qty_inputs[0].fill("5")
            
            print("   Saving new transfer...")
            await page.click("button#save-transfer-btn")
            await page.wait_for_url("http://127.0.0.1:5000/inventory/transfers")
            
            # Refetch edit buttons
            await page.wait_for_load_state("networkidle")
            edit_buttons = await page.query_selector_all("a:has-text('Edit')")
            
        print("5. Getting initial inventory from DB for Product 1...")
        initial_source = get_product_stock(1, 1)
        initial_dest = get_product_stock(1, 2)
        print(f"   Source (Main): {initial_source}, Dest (LA): {initial_dest}")
            
        print("6. Clicking 'Edit' on the first transfer...")
        await edit_buttons[0].click()
        
        print("7. Waiting for Edit Transfer page to load...")
        await page.wait_for_selector("h2:has-text('Edit Transfer')")
        
        print("8. Modifying a quantity in the transfer...")
        # Wait for items to load in the table
        await page.wait_for_selector(".qty-input")
        qty_inputs = await page.query_selector_all(".qty-input")
        
        # Increase the first product's transfer quantity by 2
        old_val = await qty_inputs[0].input_value()
        new_val = str(float(old_val) + 2)
        await qty_inputs[0].fill(new_val)
        print(f"   Changed transfer quantity from {old_val} to {new_val}")
        
        print("9. Saving the edited transfer...")
        await page.click("button#save-transfer-btn")
        
        print("10. Verifying successful save and redirect...")
        await page.wait_for_url("http://127.0.0.1:5000/inventory/transfers")
        
        print("11. Verifying inventory changes in DB...")
        final_source = get_product_stock(1, 1)
        final_dest = get_product_stock(1, 2)
        print(f"   Final Source (Main): {final_source}, Final Dest (LA): {final_dest}")
        
        # If we increased transfer by 2, source should be -2, dest should be +2
        assert final_source == initial_source - 2, f"Source stock mismatch! Expected {initial_source - 2}, got {final_source}"
        assert final_dest == initial_dest + 2, f"Dest stock mismatch! Expected {initial_dest + 2}, got {final_dest}"
        
        print("Success! The edited transfer correctly adjusted inventory in the database.")
        
        await browser.close()

if __name__ == "__main__":
    asyncio.run(main())
