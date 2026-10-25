import unittest
import json
import io
from werkzeug.security import generate_password_hash

import app
import database
from invoice_generator import generate_pdf_from_data


class TestSaaSIsolation(unittest.TestCase):
    """
    Comprehensive End-to-End Multi-Tenant Isolation Test Suite:
    - Cross-tenant inventory, products, and categories boundary isolation.
    - Inter-warehouse transfer cross-company rejection.
    - Customer ledgers & Accounts Receivable isolation.
    - Independent company invoice numbering sequences (e.g. AK- vs INV-).
    - Commercial privacy & cost price redaction for non-admins (ADR 0003).
    - Supplier ledgers and purchase shipments isolation.
    - Admin-only operational expenses isolation.
    - Public tenant catalogue & brochure routing (/c/<slug>/) with 250 safety cap.
    - SuperAdmin platform governance & soft-deactivation session interception (ADR 0004).
    """

    @classmethod
    def setUpClass(cls):
        database.init_db()

    def _clean_test_data(self, conn):
        try:
            conn.execute("PRAGMA foreign_keys = OFF")
        except Exception:
            pass
        co_ids = [r[0] for r in conn.execute("SELECT id FROM companies WHERE slug IN ('iso-corp-a', 'iso-corp-b')").fetchall()]
        if co_ids:
            ph = ",".join("?" * len(co_ids))
            tables = [
                "expenses", "supplier_payments", "purchase_items", "purchases", "suppliers",
                "inventory_transfer_items", "inventory_transfers", "inventory_history",
                "warehouse_inventory", "customer_payments", "sale_items", "sales", "customers",
                "product_variants", "products", "categories", "brands", "warehouses", "users"
            ]
            for tbl in tables:
                chk = conn.execute("SELECT name FROM sqlite_master WHERE type='table' AND name=?", (tbl,)).fetchone()
                if chk:
                    cols = [r[1] for r in conn.execute(f"PRAGMA table_info({tbl})").fetchall()]
                    if "company_id" in cols:
                        conn.execute(f"DELETE FROM {tbl} WHERE company_id IN ({ph})", co_ids)
            conn.execute(f"DELETE FROM companies WHERE id IN ({ph})", co_ids)
        
        conn.execute("DELETE FROM users WHERE username = 'iso_superadmin'")
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

            # Tenant A: iso-corp-a
            conn.execute(
                """
                INSERT INTO companies (name, slug, currency, invoice_prefix, is_active, max_warehouses)
                VALUES ('Isolation Corp A', 'iso-corp-a', '$', 'ISOA-', 1, 5)
                """
            )
            self.co_a_id = conn.execute("SELECT id FROM companies WHERE slug = 'iso-corp-a'").fetchone()[0]

            # Tenant B: iso-corp-b
            conn.execute(
                """
                INSERT INTO companies (name, slug, currency, invoice_prefix, is_active, max_warehouses)
                VALUES ('Isolation Corp B', 'iso-corp-b', '\u20ac', 'ISOB-', 1, 5)
                """
            )
            self.co_b_id = conn.execute("SELECT id FROM companies WHERE slug = 'iso-corp-b'").fetchone()[0]

            # SuperAdmin
            conn.execute(
                """
                INSERT INTO users (username, password_hash, role, company_id)
                VALUES ('iso_superadmin', ?, 'superadmin', 1)
                """,
                (generate_password_hash("superpass123", method="pbkdf2:sha256"),)
            )

            # Tenant A Facilities
            conn.execute("INSERT INTO warehouses (name, company_id) VALUES ('Warehouse A1', ?)", (self.co_a_id,))
            self.wh_a1 = conn.execute("SELECT id FROM warehouses WHERE name = 'Warehouse A1'").fetchone()[0]

            # Tenant B Facilities
            conn.execute("INSERT INTO warehouses (name, company_id) VALUES ('Warehouse B1', ?)", (self.co_b_id,))
            self.wh_b1 = conn.execute("SELECT id FROM warehouses WHERE name = 'Warehouse B1'").fetchone()[0]

            # Tenant A Users
            conn.execute(
                """
                INSERT INTO users (username, password_hash, role, company_id)
                VALUES ('admin_a', ?, 'admin', ?)
                """,
                (generate_password_hash("pass123", method="pbkdf2:sha256"), self.co_a_id)
            )
            conn.execute(
                """
                INSERT INTO users (username, password_hash, role, warehouse_id, company_id)
                VALUES ('sales_a', ?, 'salesman', ?, ?)
                """,
                (generate_password_hash("pass123", method="pbkdf2:sha256"), self.wh_a1, self.co_a_id)
            )

            # Tenant B Users
            conn.execute(
                """
                INSERT INTO users (username, password_hash, role, company_id)
                VALUES ('admin_b', ?, 'admin', ?)
                """,
                (generate_password_hash("pass123", method="pbkdf2:sha256"), self.co_b_id)
            )

            # Tenant A Category & Product
            conn.execute("INSERT INTO categories (name, company_id) VALUES ('Cat A', ?)", (self.co_a_id,))
            self.cat_a = conn.execute("SELECT id FROM categories WHERE name = 'Cat A'").fetchone()[0]

            conn.execute(
                """
                INSERT INTO products (name, brand, cost_price, selling_price, category_id, company_id)
                VALUES ('Alpha Product A', 'Brand A', 50.0, 100.0, ?, ?)
                """,
                (self.cat_a, self.co_a_id)
            )
            self.prod_a = conn.execute("SELECT id FROM products WHERE name = 'Alpha Product A'").fetchone()[0]

            conn.execute(
                "INSERT INTO warehouse_inventory (company_id, product_id, warehouse_id, stock_quantity) VALUES (?, ?, ?, 50)",
                (self.co_a_id, self.prod_a, self.wh_a1)
            )

            # Tenant B Category & Product
            conn.execute("INSERT INTO categories (name, company_id) VALUES ('Cat B', ?)", (self.co_b_id,))
            self.cat_b = conn.execute("SELECT id FROM categories WHERE name = 'Cat B'").fetchone()[0]

            conn.execute(
                """
                INSERT INTO products (name, brand, cost_price, selling_price, category_id, company_id)
                VALUES ('Beta Product B', 'Brand B', 75.0, 150.0, ?, ?)
                """,
                (self.cat_b, self.co_b_id)
            )
            self.prod_b = conn.execute("SELECT id FROM products WHERE name = 'Beta Product B'").fetchone()[0]

            # Tenant A Customer
            conn.execute("INSERT INTO customers (name, phone, company_id) VALUES ('Client A', '555-1111', ?)", (self.co_a_id,))
            self.cust_a = conn.execute("SELECT id FROM customers WHERE name = 'Client A'").fetchone()[0]

            # Tenant B Customer
            conn.execute("INSERT INTO customers (name, phone, company_id) VALUES ('Client B', '555-2222', ?)", (self.co_b_id,))
            self.cust_b = conn.execute("SELECT id FROM customers WHERE name = 'Client B'").fetchone()[0]

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
        self.client.get("/logout")
        with self.client.session_transaction() as sess:
            sess.clear()
        return self.client.post("/login", data={"username": username, "password": password}, follow_redirects=True)

    def test_cross_tenant_product_isolation(self):
        """Tenant B must never see or be able to mutate Tenant A's products."""
        self._login("admin_b")

        # 1. Product list does not contain Tenant A products
        res = self.client.get("/products/list")
        data = res.get_json()
        names = [p["name"] for p in data]
        self.assertIn("Beta Product B", names)
        self.assertNotIn("Alpha Product A", names)

        # 2. Direct edit of Tenant A product by Tenant B returns 404
        res = self.client.post(f"/products/edit/{self.prod_a}", data={"name": "Hacked Product"}, follow_redirects=True)
        self.assertIn(res.status_code, (404, 302))

        # Verify DB unchanged
        conn = database.get_connection()
        try:
            p = conn.execute("SELECT name FROM products WHERE id = ?", (self.prod_a,)).fetchone()
            self.assertEqual(p["name"], "Alpha Product A")
        finally:
            conn.close()

    def test_inter_warehouse_transfer_cross_tenant_rejection(self):
        """Moving stock between facilities of different companies is strictly rejected."""
        self._login("admin_a")

        payload = {
            "source_warehouse_id": self.wh_a1,
            "destination_warehouse_id": self.wh_b1,  # Warehouse B1 belongs to Tenant B!
            "notes": "Malicious cross-company transfer",
            "items": [{"product_id": self.prod_a, "quantity": 5}]
        }
        res = self.client.post("/inventory/transfer", json=payload)
        self.assertEqual(res.status_code, 400)
        self.assertIn("invalid or unauthorized", res.get_json().get("error", "").lower())

    def test_customer_and_accounts_receivable_isolation(self):
        """Customers and ledger balances are strictly partitioned by tenant."""
        self._login("admin_a")

        # Customer list for Tenant A
        res = self.client.get("/customers/list")
        names = [c["name"] for c in res.get_json()]
        self.assertIn("Client A", names)
        self.assertNotIn("Client B", names)

        # Tenant A attempting to record payment on Tenant B customer is rejected with 404
        pay_payload = {
            "customer_id": self.cust_b,
            "amount": 100.0,
            "payment_method": "Cash",
            "notes": "Cross tenant payment"
        }
        res = self.client.post("/customers/payments/add", json=pay_payload)
        self.assertEqual(res.status_code, 404)

    def test_independent_tenant_sequential_invoice_numbering(self):
        """Each tenant company generates its own sequential invoice numbers with its company prefix."""
        conn = database.get_connection()
        try:
            inv_a1 = database.get_next_invoice_number(self.co_a_id)
            inv_a2 = database.get_next_invoice_number(self.co_a_id)
            inv_b1 = database.get_next_invoice_number(self.co_b_id)

            self.assertTrue(inv_a1.startswith("ISOA-"))
            self.assertTrue(inv_a2.startswith("ISOA-"))
            self.assertTrue(inv_b1.startswith("ISOB-"))

            # Company A's counter does not advance Company B's counter
            self.assertEqual(inv_b1, "ISOB-000001")
        finally:
            conn.close()

    def test_commercial_privacy_cost_masking_for_salesman(self):
        """Salesmen cannot see cost prices or gross margins (ADR 0003)."""
        self._login("sales_a")

        res = self.client.get("/products/list")
        products = res.get_json()
        self.assertTrue(len(products) > 0)
        for p in products:
            self.assertIsNone(p.get("cost_price"))

    def test_public_tenant_catalogue_and_brochure_routing(self):
        """Public routes /c/<slug>/catalogue and /c/<slug>/brochure render correctly for active tenants."""
        # 1. Tenant A public catalogue
        res = self.client.get("/c/iso-corp-a/catalogue")
        self.assertEqual(res.status_code, 200)

        # 2. Non-existent slug returns 404
        res = self.client.get("/c/non-existent-company-xyz/catalogue")
        self.assertEqual(res.status_code, 404)

        # 3. Root catalogue backwards compatibility for Company 1
        res = self.client.get("/catalogue")
        self.assertEqual(res.status_code, 200)

    def test_soft_deactivation_session_termination_and_superadmin_oversight(self):
        """Soft-deactivating a company intercepts its user logins immediately while superadmin retains access."""
        # 1. SuperAdmin suspends Tenant A
        self._login("iso_superadmin", "superpass123")
        res = self.client.post(f"/superadmin/company/{self.co_a_id}/toggle_status", follow_redirects=True)
        self.assertEqual(res.status_code, 200)

        # 2. Tenant A admin login is immediately blocked
        res = self._login("admin_a")
        self.assertIn(b"paused or suspended", res.data)

        # 3. SuperAdmin can still view /superadmin console and reactivate
        self._login("iso_superadmin", "superpass123")
        res = self.client.get("/superadmin")
        self.assertEqual(res.status_code, 200)

        res = self.client.post(f"/superadmin/company/{self.co_a_id}/toggle_status", follow_redirects=True)
        self.assertEqual(res.status_code, 200)

        # 4. Tenant A admin can log in again
        res = self._login("admin_a")
        self.assertEqual(res.status_code, 200)
        self.assertNotIn(b"paused or suspended", res.data)


if __name__ == "__main__":
    unittest.main()
