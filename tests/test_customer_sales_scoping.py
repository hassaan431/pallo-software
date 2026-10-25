import unittest
import json
from werkzeug.security import generate_password_hash

import app
import database


class TestCustomerSalesScoping(unittest.TestCase):
    """
    Test suite for Ticket 07:
    - Multi-tenant customer ledger scoping and isolation.
    - Tenant-specific sequential invoice numbers (e.g. TC1-000001 vs TC2-000001, and AK- continuity).
    - Sales creation, listing, details, and PDF multi-tenant isolation.
    - Commercial privacy & profit margin masking on sales for non-admins per ADR 0003.
    - Quotation to sale conversion with tenant-specific prefix.
    - POS checkout multi-tenant scoping.
    """

    @classmethod
    def setUpClass(cls):
        database.init_db()

    def _clean_test_data(self, conn):
        try:
            conn.execute("PRAGMA foreign_keys = OFF")
        except Exception:
            pass
        co_ids = [r[0] for r in conn.execute("SELECT id FROM companies WHERE slug IN ('test-sales-c1', 'test-sales-c2')").fetchall()]
        if co_ids:
            ph = ",".join("?" * len(co_ids))
            tables = [
                "inventory_history", "sale_items", "sales", "warehouse_inventory",
                "products", "customers", "users", "warehouses"
            ]
            for tbl in tables:
                chk = conn.execute("SELECT name FROM sqlite_master WHERE type='table' AND name=?", (tbl,)).fetchone()
                if chk:
                    cols = [r[1] for r in conn.execute(f"PRAGMA table_info({tbl})").fetchall()]
                    if "company_id" in cols:
                        conn.execute(f"DELETE FROM {tbl} WHERE company_id IN ({ph})", co_ids)
            conn.execute(f"DELETE FROM companies WHERE id IN ({ph})", co_ids)
        conn.commit()
        try:
            conn.execute("PRAGMA foreign_keys = ON")
        except Exception:
            pass

    def setUp(self):
        self.app = app.app
        self.app.config["TESTING"] = True
        self.app.config["WTF_CSRF_ENABLED"] = False
        self.client = self.app.test_client()

        conn = database.get_connection()
        try:
            self._clean_test_data(conn)

            # 1. Company 1 setup
            cur = conn.execute(
                "INSERT INTO companies (name, slug, currency, invoice_prefix, starting_invoice_number, is_active) "
                "VALUES ('Sales Co 1', 'test-sales-c1', '$', 'S1-', 1, 1)"
            )
            self.c1_id = cur.lastrowid if cur.lastrowid else conn.execute("SELECT id FROM companies WHERE slug = 'test-sales-c1'").fetchone()["id"]

            cur_w1 = conn.execute(
                "INSERT INTO warehouses (company_id, name, location) VALUES (?, 'Warehouse 1', 'Loc 1')",
                (self.c1_id,)
            )
            self.w1_id = cur_w1.lastrowid if cur_w1.lastrowid else conn.execute("SELECT id FROM warehouses WHERE company_id = ? AND name = 'Warehouse 1'", (self.c1_id,)).fetchone()["id"]

            pwd = generate_password_hash("pass123")
            conn.execute(
                "INSERT INTO users (company_id, username, password_hash, role, is_active, warehouse_id) "
                "VALUES (?, 'admin_c1', ?, 'admin', 1, ?)",
                (self.c1_id, pwd, self.w1_id)
            )
            conn.execute(
                "INSERT INTO users (company_id, username, password_hash, role, is_active, warehouse_id) "
                "VALUES (?, 'salesman_c1', ?, 'salesman', 1, ?)",
                (self.c1_id, pwd, self.w1_id)
            )

            # Customer for C1
            cur_cust1 = conn.execute(
                "INSERT INTO customers (company_id, name, phone, email, area) VALUES (?, 'Customer One', '111-1111', 'c1@test.com', 'North')",
                (self.c1_id,)
            )
            self.cust1_id = cur_cust1.lastrowid

            # Product for C1
            cur_prod1 = conn.execute(
                "INSERT INTO products (company_id, name, brand, cost_price, selling_price, stock_quantity) "
                "VALUES (?, 'Product One', 'Brand A', 10.0, 25.0, 100)",
                (self.c1_id,)
            )
            self.prod1_id = cur_prod1.lastrowid
            conn.execute(
                "INSERT INTO warehouse_inventory (company_id, warehouse_id, product_id, stock_quantity) VALUES (?, ?, ?, 100)",
                (self.c1_id, self.w1_id, self.prod1_id)
            )

            # 2. Company 2 setup
            cur2 = conn.execute(
                "INSERT INTO companies (name, slug, currency, invoice_prefix, starting_invoice_number, is_active) "
                "VALUES ('Sales Co 2', 'test-sales-c2', '€', 'S2-', 500, 1)"
            )
            self.c2_id = cur2.lastrowid if cur2.lastrowid else conn.execute("SELECT id FROM companies WHERE slug = 'test-sales-c2'").fetchone()["id"]

            cur_w2 = conn.execute(
                "INSERT INTO warehouses (company_id, name, location) VALUES (?, 'Warehouse 2', 'Loc 2')",
                (self.c2_id,)
            )
            self.w2_id = cur_w2.lastrowid if cur_w2.lastrowid else conn.execute("SELECT id FROM warehouses WHERE company_id = ? AND name = 'Warehouse 2'", (self.c2_id,)).fetchone()["id"]

            conn.execute(
                "INSERT INTO users (company_id, username, password_hash, role, is_active, warehouse_id) "
                "VALUES (?, 'admin_c2', ?, 'admin', 1, ?)",
                (self.c2_id, pwd, self.w2_id)
            )

            cur_cust2 = conn.execute(
                "INSERT INTO customers (company_id, name, phone, email, area) VALUES (?, 'Customer Two', '222-2222', 'c2@test.com', 'South')",
                (self.c2_id,)
            )
            self.cust2_id = cur_cust2.lastrowid

            cur_prod2 = conn.execute(
                "INSERT INTO products (company_id, name, brand, cost_price, selling_price, stock_quantity) "
                "VALUES (?, 'Product Two', 'Brand B', 50.0, 80.0, 50)",
                (self.c2_id,)
            )
            self.prod2_id = cur_prod2.lastrowid
            conn.execute(
                "INSERT INTO warehouse_inventory (company_id, warehouse_id, product_id, stock_quantity) VALUES (?, ?, ?, 50)",
                (self.c2_id, self.w2_id, self.prod2_id)
            )

            conn.commit()
        finally:
            conn.close()

    def tearDown(self):
        conn = database.get_connection()
        try:
            self._clean_test_data(conn)
        finally:
            conn.close()

    def _login(self, username, password="pass123"):
        self.client.get("/logout", follow_redirects=True)
        return self.client.post("/login", data={"username": username, "password": password}, follow_redirects=True)

    def test_tenant_invoice_number_generation(self):
        """Test that get_next_invoice_number respects company prefix and sequence."""
        inv_c1_1 = database.get_next_invoice_number(self.c1_id)
        self.assertEqual(inv_c1_1, "S1-000001")

        inv_c2_1 = database.get_next_invoice_number(self.c2_id)
        self.assertEqual(inv_c2_1, "S2-000500")

        # Simulate sale for C1 and verify increment
        conn = database.get_connection()
        try:
            conn.execute(
                "INSERT INTO sales (company_id, invoice_number, customer_id, invoice_date, subtotal, grand_total, status) "
                "VALUES (?, 'S1-000001', ?, '2026-10-25', 25.0, 25.0, 'paid')",
                (self.c1_id, self.cust1_id)
            )
            conn.commit()
        finally:
            conn.close()

        inv_c1_2 = database.get_next_invoice_number(self.c1_id)
        self.assertEqual(inv_c1_2, "S1-000002")
        # Ensure C2's sequence was NOT affected
        inv_c2_check = database.get_next_invoice_number(self.c2_id)
        self.assertEqual(inv_c2_check, "S2-000500")

    def test_customer_isolation_between_companies(self):
        """Test customer CRUD and list endpoints isolate tenants."""
        # 1. Admin C1 sees only Customer One
        self._login("admin_c1")
        resp = self.client.get("/customers/list")
        self.assertEqual(resp.status_code, 200)
        c1_customers = resp.get_json()
        c1_names = [c["name"] for c in c1_customers]
        self.assertIn("Customer One", c1_names)
        self.assertNotIn("Customer Two", c1_names)

        # 2. Admin C1 tries to edit Customer Two -> 404
        edit_resp = self.client.post(f"/customers/edit/{self.cust2_id}", data={
            "full_name": "Hacked Customer Two",
            "bill_address": "Hacked Billing",
            "phone": "999",
            "email": "hacked@test.com",
            "area": "Nowhere"
        })
        self.assertEqual(edit_resp.status_code, 404)

        # 3. Admin C1 tries to delete Customer Two -> 404
        del_resp = self.client.post(f"/customers/delete/{self.cust2_id}")
        self.assertEqual(del_resp.status_code, 404)

        # 4. Admin C1 creates a new customer -> gets company_id = c1_id
        add_resp = self.client.post("/customers/add", data={
            "full_name": "Customer One B",
            "bill_address": "123 Main St",
            "phone": "111-2222",
            "email": "c1b@test.com",
            "area": "West"
        }, follow_redirects=True)
        self.assertEqual(add_resp.status_code, 200)

        conn = database.get_connection()
        try:
            row = conn.execute("SELECT company_id FROM customers WHERE name = 'Customer One B'").fetchone()
            self.assertIsNotNone(row)
            self.assertEqual(row["company_id"], self.c1_id)
        finally:
            conn.close()

    def test_sales_creation_and_details_isolation(self):
        """Test sales creation scopes to company and details route enforces tenant isolation."""
        self._login("admin_c1")

        # Create a sale in C1
        items_json = json.dumps([{
            "product_id": self.prod1_id,
            "description": "Product One Item",
            "qty": 2,
            "rate": 25.0,
            "amount": 50.0,
            "packing_multiplier": 1.0,
            "print_dual_units": 0
        }])

        resp = self.client.post("/sales/new", data={
            "customer_id": str(self.cust1_id),
            "invoice_date": "2026-10-25",
            "payment_type": "cash",
            "items_json": items_json,
            "warehouse_id": str(self.w1_id)
        }, follow_redirects=True)
        self.assertEqual(resp.status_code, 200)

        conn = database.get_connection()
        try:
            sale = conn.execute("SELECT * FROM sales WHERE customer_id = ? AND company_id = ?", (self.cust1_id, self.c1_id)).fetchone()
            self.assertIsNotNone(sale)
            sale_id = sale["id"]
            self.assertTrue(sale["invoice_number"].startswith("S1-"))
            self.assertEqual(sale["company_id"], self.c1_id)
        finally:
            conn.close()

        # Admin C1 can view details
        det_c1 = self.client.get(f"/sales/{sale_id}/details")
        self.assertEqual(det_c1.status_code, 200)
        data_c1 = det_c1.get_json()
        self.assertEqual(data_c1["grand_total"], 50.0)
        self.assertEqual(data_c1["profit_amount"], 30.0)  # 50 - (2 * 10 cost) = 30

        # Login as Admin C2 and attempt to view C1's sale details -> 404
        self._login("admin_c2")
        det_c2 = self.client.get(f"/sales/{sale_id}/details")
        self.assertEqual(det_c2.status_code, 404)

    def test_commercial_privacy_salesman_cost_masking(self):
        """Test ADR 0003: salesmen cannot see cost price, total cost, or profit margins on sales data or details."""
        # Insert a sale for C1
        conn = database.get_connection()
        try:
            cur = conn.execute(
                "INSERT INTO sales (company_id, invoice_number, customer_id, invoice_date, subtotal, grand_total, status, salesman_id, warehouse_id) "
                "VALUES (?, 'S1-000001', ?, '2026-10-25', 25.0, 25.0, 'paid', (SELECT id FROM users WHERE username = 'salesman_c1'), ?)",
                (self.c1_id, self.cust1_id, self.w1_id)
            )
            sale_id = cur.lastrowid
            conn.execute(
                "INSERT INTO sale_items (company_id, sale_id, product_id, description, qty, rate, amount, cost_price) "
                "VALUES (?, ?, ?, 'Prod 1', 1, 25.0, 25.0, 10.0)",
                (self.c1_id, sale_id, self.prod1_id)
            )
            conn.commit()
        finally:
            conn.close()

        # 1. Login as Salesman C1
        self._login("salesman_c1")

        # Check /sales/data
        s_data = self.client.get("/sales/data").get_json()
        self.assertGreater(len(s_data), 0)
        row = s_data[0]
        self.assertIsNone(row.get("profit_margin"))
        self.assertIsNone(row.get("profit_amount"))
        self.assertIsNone(row.get("total_cost"))

        # Check /sales/<id>/details
        det = self.client.get(f"/sales/{sale_id}/details").get_json()
        self.assertIsNone(det.get("profit_margin"))
        self.assertIsNone(det.get("profit_amount"))
        self.assertIsNone(det.get("total_cost"))

        # 2. Login as Admin C1
        self._login("admin_c1")
        admin_det = self.client.get(f"/sales/{sale_id}/details").get_json()
        self.assertIsNotNone(admin_det.get("profit_margin"))
        self.assertIsNotNone(admin_det.get("profit_amount"))
        self.assertEqual(admin_det.get("profit_amount"), 15.0)  # 25 - 10 = 15

    def test_pos_submit_order_scoping(self):
        """Test POS checkout assigns tenant invoice prefix, scopes customer and sale to company."""
        self._login("admin_c2")

        payload = {
            "customer_name": "POS Walkin Customer",
            "customer_phone": "555-1234",
            "warehouse_id": self.w2_id,
            "payment_type": "cash",
            "items": [{
                "id": self.prod2_id,
                "qty": 3,
                "packing_multiplier": 1.0
            }]
        }

        resp = self.client.post("/pos/submit_order", json=payload)
        self.assertEqual(resp.status_code, 200)
        res_data = resp.get_json()
        self.assertTrue(res_data["ok"])
        self.assertTrue(res_data["invoice_number"].startswith("S2-0005"))

        conn = database.get_connection()
        try:
            sale = conn.execute("SELECT * FROM sales WHERE id = ?", (res_data["sale_id"],)).fetchone()
            self.assertEqual(sale["company_id"], self.c2_id)
            self.assertEqual(sale["grand_total"], 240.0)  # 3 * 80.0

            # Verify customer created with c2_id
            cust = conn.execute("SELECT * FROM customers WHERE id = ?", (sale["customer_id"],)).fetchone()
            self.assertEqual(cust["company_id"], self.c2_id)

            # Verify inventory deducted
            inv = conn.execute("SELECT stock_quantity FROM warehouse_inventory WHERE product_id = ? AND warehouse_id = ?", (self.prod2_id, self.w2_id)).fetchone()
            self.assertEqual(inv["stock_quantity"], 47.0)  # 50 - 3 = 47
        finally:
            conn.close()

    def test_quotation_conversion_uses_tenant_prefix(self):
        """Test that converting a quotation for Company 2 converts Q-000500 to S2-000500 instead of hardcoded AK-."""
        self._login("admin_c2")

        # Create a quote in C2
        items_json = json.dumps([{
            "product_id": self.prod2_id,
            "description": "Product Two Quote",
            "qty": 1,
            "rate": 80.0,
            "amount": 80.0,
            "packing_multiplier": 1.0,
            "print_dual_units": 0
        }])

        self.client.post("/sales/new", data={
            "customer_id": str(self.cust2_id),
            "invoice_date": "2026-10-25",
            "payment_type": "credit",
            "items_json": items_json,
            "warehouse_id": str(self.w2_id),
            "generate_quote": "1"
        }, follow_redirects=True)

        conn = database.get_connection()
        try:
            quote = conn.execute("SELECT * FROM sales WHERE customer_id = ? AND status = 'quote'", (self.cust2_id,)).fetchone()
            self.assertIsNotNone(quote)
            quote_id = quote["id"]
            self.assertTrue(quote["invoice_number"].startswith("Q-"))
        finally:
            conn.close()

        # Mark quote as sale
        mark_resp = self.client.post(f"/sales/{quote_id}/mark_sale", json={"amount": 80.0, "payment_method": "Cash"})
        self.assertEqual(mark_resp.status_code, 200)
        mark_data = mark_resp.get_json()
        self.assertTrue(mark_data["success"])
        # Should start with S2- not AK-
        self.assertTrue(mark_data["new_invoice_number"].startswith("S2-"))
        self.assertFalse(mark_data["new_invoice_number"].startswith("AK-"))


if __name__ == "__main__":
    unittest.main()
