import unittest
import sqlite3
from pathlib import Path
from werkzeug.security import generate_password_hash

import app
import database


class TestProductScopingAndCostMasking(unittest.TestCase):
    """
    Test suite for Ticket 06:
    - Multi-tenant isolation for products, categories, brands, warehouse inventory.
    - Commercial privacy and cost price masking per ADR 0003 (salesman / non-admin).
    """

    @classmethod
    def setUpClass(cls):
        database.init_db()

    def _clean_test_data(self, conn):
        try:
            conn.execute("PRAGMA foreign_keys = OFF")
        except Exception:
            pass
        co_ids = [r[0] for r in conn.execute("SELECT id FROM companies WHERE slug IN ('test-co-1', 'test-co-2')").fetchall()]
        if co_ids:
            ph = ",".join("?" * len(co_ids))
            tables = [
                "inventory_transfer_items", "inventory_transfers", "inventory_history",
                "sale_items", "sales", "purchase_items", "purchases", "supplier_payments",
                "customer_payments", "expenses", "warehouse_inventory", "product_variants",
                "products", "suppliers", "customers", "categories", "brands", "users", "warehouses"
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

        # Seed Company 1 and Company 2 in DB
        conn = database.get_connection()
        try:
            self._clean_test_data(conn)

            # 1. Company 1
            cur = conn.execute(
                "INSERT INTO companies (name, slug, currency, invoice_prefix, starting_invoice_number, is_active) "
                "VALUES ('Test Company 1', 'test-co-1', '$', 'TC1-', 1, 1)"
            )
            self.c1_id = cur.lastrowid if cur.lastrowid else conn.execute("SELECT id FROM companies WHERE slug = 'test-co-1'").fetchone()["id"]

            cur_w1 = conn.execute(
                "INSERT INTO warehouses (company_id, name, location) VALUES (?, 'W1 Main', 'Loc 1')",
                (self.c1_id,)
            )
            self.w1_id = cur_w1.lastrowid if cur_w1.lastrowid else conn.execute("SELECT id FROM warehouses WHERE company_id = ? AND name = 'W1 Main'", (self.c1_id,)).fetchone()["id"]

            # Users for C1
            pwd = generate_password_hash("password123")
            conn.execute(
                "INSERT INTO users (company_id, username, password_hash, role, is_active, warehouse_id) "
                "VALUES (?, 'test_admin_c1', ?, 'admin', 1, ?)",
                (self.c1_id, pwd, self.w1_id)
            )
            conn.execute(
                "INSERT INTO users (company_id, username, password_hash, role, is_active, warehouse_id) "
                "VALUES (?, 'test_sales_c1', ?, 'salesman', 1, ?)",
                (self.c1_id, pwd, self.w1_id)
            )
            conn.execute(
                "INSERT INTO users (company_id, username, password_hash, role, is_active, warehouse_id) "
                "VALUES (?, 'test_wm_c1', ?, 'warehouse_manager', 1, ?)",
                (self.c1_id, pwd, self.w1_id)
            )

            # 2. Company 2
            cur2 = conn.execute(
                "INSERT INTO companies (name, slug, currency, invoice_prefix, starting_invoice_number, is_active) "
                "VALUES ('Test Company 2', 'test-co-2', 'EUR', 'TC2-', 1, 1)"
            )
            self.c2_id = cur2.lastrowid if cur2.lastrowid else conn.execute("SELECT id FROM companies WHERE slug = 'test-co-2'").fetchone()["id"]

            cur_w2 = conn.execute(
                "INSERT INTO warehouses (company_id, name, location) VALUES (?, 'W2 Main', 'Loc 2')",
                (self.c2_id,)
            )
            self.w2_id = cur_w2.lastrowid if cur_w2.lastrowid else conn.execute("SELECT id FROM warehouses WHERE company_id = ? AND name = 'W2 Main'", (self.c2_id,)).fetchone()["id"]

            conn.execute(
                "INSERT INTO users (company_id, username, password_hash, role, is_active, warehouse_id) "
                "VALUES (?, 'test_admin_c2', ?, 'admin', 1, ?)",
                (self.c2_id, pwd, self.w2_id)
            )

            # Seed Category & Brand for C1
            conn.execute("INSERT INTO categories (company_id, name) VALUES (?, 'TEST_CAT_C1')", (self.c1_id,))
            self.cat1_id = conn.execute("SELECT id FROM categories WHERE company_id = ? AND name = 'TEST_CAT_C1'", (self.c1_id,)).fetchone()["id"]

            conn.execute("INSERT INTO brands (company_id, name) VALUES (?, 'TEST_BRAND_C1')", (self.c1_id,))
            self.brand1_id = conn.execute("SELECT id FROM brands WHERE company_id = ? AND name = 'TEST_BRAND_C1'", (self.c1_id,)).fetchone()["id"]

            # Seed Product for C1 (Cost $40, Selling $100, Stock 50)
            conn.execute(
                """
                INSERT INTO products (company_id, name, category_id, brand, unit, cost_price, selling_price, is_public, is_open)
                VALUES (?, 'TEST_PROD_C1', ?, 'TEST_BRAND_C1', 'Each', 40.0, 100.0, 1, 0)
                """,
                (self.c1_id, self.cat1_id)
            )
            self.prod1_id = conn.execute("SELECT id FROM products WHERE company_id = ? AND name = 'TEST_PROD_C1'", (self.c1_id,)).fetchone()["id"]
            conn.execute(
                "INSERT INTO warehouse_inventory (company_id, product_id, warehouse_id, stock_quantity) VALUES (?, ?, ?, 50)",
                (self.c1_id, self.prod1_id, self.w1_id)
            )

            # Seed Category, Brand & Product for C2 (Cost $15, Selling $35, Stock 20)
            conn.execute("INSERT INTO categories (company_id, name) VALUES (?, 'TEST_CAT_C2')", (self.c2_id,))
            self.cat2_id = conn.execute("SELECT id FROM categories WHERE company_id = ? AND name = 'TEST_CAT_C2'", (self.c2_id,)).fetchone()["id"]

            conn.execute("INSERT INTO brands (company_id, name) VALUES (?, 'TEST_BRAND_C2')", (self.c2_id,))
            self.brand2_id = conn.execute("SELECT id FROM brands WHERE company_id = ? AND name = 'TEST_BRAND_C2'", (self.c2_id,)).fetchone()["id"]

            conn.execute(
                """
                INSERT INTO products (company_id, name, category_id, brand, unit, cost_price, selling_price, is_public, is_open)
                VALUES (?, 'TEST_PROD_C2', ?, 'TEST_BRAND_C2', 'Box', 15.0, 35.0, 1, 0)
                """,
                (self.c2_id, self.cat2_id)
            )
            self.prod2_id = conn.execute("SELECT id FROM products WHERE company_id = ? AND name = 'TEST_PROD_C2'", (self.c2_id,)).fetchone()["id"]
            conn.execute(
                "INSERT INTO warehouse_inventory (company_id, product_id, warehouse_id, stock_quantity) VALUES (?, ?, ?, 20)",
                (self.c2_id, self.prod2_id, self.w2_id)
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

    def _login(self, username, password="password123"):
        return self.client.post("/login", data={"username": username, "password": password}, follow_redirects=True)

    def test_products_list_cross_tenant_isolation(self):
        """Verify Tenant A only sees Tenant A's products, and Tenant B only sees Tenant B's products."""
        # Tenant A (Company 1 Admin)
        self._login("test_admin_c1")
        res1 = self.client.get("/products/list")
        self.assertEqual(res1.status_code, 200)
        items1 = res1.get_json()
        names1 = [i["name"] for i in items1]
        self.assertIn("TEST_PROD_C1", names1)
        self.assertNotIn("TEST_PROD_C2", names1)

        # Logout and log in as Tenant B (Company 2 Admin)
        self.client.get("/logout", follow_redirects=True)
        self._login("test_admin_c2")
        res2 = self.client.get("/products/list")
        self.assertEqual(res2.status_code, 200)
        items2 = res2.get_json()
        names2 = [i["name"] for i in items2]
        self.assertIn("TEST_PROD_C2", names2)
        self.assertNotIn("TEST_PROD_C1", names2)

    def test_products_search_cross_tenant_isolation(self):
        """Verify product search endpoint respects tenant scoping."""
        self._login("test_admin_c1")
        res = self.client.get("/products/search?q=TEST_PROD")
        self.assertEqual(res.status_code, 200)
        results = res.get_json()
        names = [r["name"] for r in results]
        self.assertIn("TEST_PROD_C1", names)
        self.assertNotIn("TEST_PROD_C2", names)

    def test_cost_price_masking_for_salesman_and_non_admin(self):
        """
        Verify ADR 0003: Cost price is revealed to admin, but strictly masked (None)
        to salesman and warehouse manager in /products/list and /products/search.
        """
        # 1. Admin sees cost_price
        self._login("test_admin_c1")
        res_admin = self.client.get("/products/list")
        p_admin = next(p for p in res_admin.get_json() if p["name"] == "TEST_PROD_C1")
        self.assertEqual(p_admin["cost_price"], 40.0)

        res_search_admin = self.client.get("/products/search?q=TEST_PROD_C1")
        ps_admin = next(p for p in res_search_admin.get_json() if p["name"] == "TEST_PROD_C1")
        self.assertEqual(ps_admin["cost_price"], 40.0)

        # 2. Salesman has cost_price masked to None
        self.client.get("/logout", follow_redirects=True)
        self._login("test_sales_c1")
        res_sales = self.client.get("/products/list")
        p_sales = next(p for p in res_sales.get_json() if p["name"] == "TEST_PROD_C1")
        self.assertIsNone(p_sales["cost_price"], "Salesman must NOT receive cost_price")

        res_search_sales = self.client.get("/products/search?q=TEST_PROD_C1")
        ps_sales = next(p for p in res_search_sales.get_json() if p["name"] == "TEST_PROD_C1")
        self.assertIsNone(ps_sales["cost_price"], "Salesman must NOT receive cost_price in search")

        # 3. Warehouse manager has cost_price masked to None
        self.client.get("/logout", follow_redirects=True)
        self._login("test_wm_c1")
        res_wm = self.client.get("/products/list")
        p_wm = next(p for p in res_wm.get_json() if p["name"] == "TEST_PROD_C1")
        self.assertIsNone(p_wm["cost_price"], "Warehouse manager must NOT receive cost_price in API")

    def test_categories_cross_tenant_isolation_and_mutations(self):
        """Verify category listing, addition, editing, and deletion are scoped per tenant."""
        self._login("test_admin_c1")

        # Listing
        res = self.client.get("/categories")
        cats = res.get_json()
        cat_names = [c["name"] for c in cats]
        self.assertIn("TEST_CAT_C1", cat_names)
        self.assertNotIn("TEST_CAT_C2", cat_names)

        # Tenant 1 cannot edit Tenant 2's category
        res_edit_cross = self.client.post(
            f"/categories/edit/{self.cat2_id}",
            json={"name": "HACKED_CAT"},
            headers={"X-Requested-With": "fetch"}
        )
        self.assertIn(res_edit_cross.status_code, (400, 404))

        # Tenant 1 cannot delete Tenant 2's category
        res_del_cross = self.client.post(
            f"/categories/delete/{self.cat2_id}",
            headers={"X-Requested-With": "fetch"}
        )
        self.assertIn(res_del_cross.status_code, (400, 404))

    def test_brands_cross_tenant_isolation_and_mutations(self):
        """Verify brand listing, addition, and editing are scoped per tenant."""
        self._login("test_admin_c1")

        # Listing
        res = self.client.get("/brands/list")
        brands = res.get_json()
        brand_names = [b["name"] for b in brands]
        self.assertIn("TEST_BRAND_C1", brand_names)
        self.assertNotIn("TEST_BRAND_C2", brand_names)

        # Brand search
        res_search = self.client.get("/brands/search?q=TEST_BRAND")
        search_brands = res_search.get_json()
        self.assertIn("TEST_BRAND_C1", search_brands)
        self.assertNotIn("TEST_BRAND_C2", search_brands)

    def test_cross_tenant_product_mutation_blocked(self):
        """Verify Tenant 1 cannot edit, delete, or adjust stock on Tenant 2's product."""
        self._login("test_admin_c1")

        # Adjust stock on Tenant 2 product
        res_adj = self.client.post(
            "/inventory/adjust_stock",
            data={"product_id": self.prod2_id, "warehouse_id": self.w1_id, "new_stock": 999},
            follow_redirects=True
        )
        self.assertIn(b"Product not found", res_adj.data)

        # Verify stock was NOT altered
        conn = database.get_connection()
        try:
            row = conn.execute("SELECT stock_quantity FROM warehouse_inventory WHERE product_id = ?", (self.prod2_id,)).fetchone()
            self.assertEqual(float(row["stock_quantity"]), 20.0)
        finally:
            conn.close()

        # Delete Tenant 2 product
        res_del = self.client.post(
            f"/inventory/delete/{self.prod2_id}",
            headers={"X-Requested-With": "fetch"}
        )
        self.assertEqual(res_del.status_code, 404)

        # Edit Tenant 2 product
        res_edit = self.client.post(
            f"/inventory/edit/{self.prod2_id}",
            data={
                "product_name": "HACKED_NAME",
                "brand": "TEST_BRAND_C1",
                "category_id": self.cat1_id,
                "unit": "Each",
                "cost_price": "1.0",
                "selling_price": "2.0"
            },
            follow_redirects=True
        )
        self.assertIn(b"Product not found", res_edit.data)

    def test_warehouse_manager_edit_product_preserves_cost_price(self):
        """
        Verify that when a warehouse manager edits catalog fields (name, brand, etc.),
        the existing sensitive supplier cost_price is preserved and not zeroed.
        """
        self._login("test_wm_c1")
        res = self.client.post(
            f"/inventory/edit/{self.prod1_id}",
            data={
                "product_name": "TEST_PROD_C1_UPDATED",
                "brand": "TEST_BRAND_C1",
                "category_id": self.cat1_id,
                "unit": "Each",
                "cost_price": "0",  # non-admin form submits 0 or empty
                "selling_price": "120.0"
            },
            follow_redirects=True
        )
        self.assertEqual(res.status_code, 200)

        conn = database.get_connection()
        try:
            prod = conn.execute("SELECT name, cost_price, selling_price FROM products WHERE id = ?", (self.prod1_id,)).fetchone()
            self.assertEqual(prod["name"], "TEST_PROD_C1_UPDATED")
            self.assertEqual(float(prod["cost_price"]), 40.0, "Cost price must be preserved!")
            self.assertEqual(float(prod["selling_price"]), 120.0)
        finally:
            conn.close()

    def test_inventory_download_csv_cost_redaction_for_non_admin(self):
        """Verify CSV download redacts Cost Price and Stock Value for non-admin roles."""
        # Admin export includes Cost Price
        self._login("test_admin_c1")
        res_admin = self.client.get("/inventory/download_csv")
        csv_admin = res_admin.data.decode("utf-8")
        self.assertIn("Cost Price", csv_admin)
        self.assertIn("Stock Value", csv_admin)

        # Warehouse Manager export redacts Cost Price and Stock Value
        self.client.get("/logout", follow_redirects=True)
        self._login("test_wm_c1")
        res_wm = self.client.get("/inventory/download_csv")
        csv_wm = res_wm.data.decode("utf-8")
        self.assertNotIn("Cost Price", csv_wm)
        self.assertNotIn("Stock Value", csv_wm)
        self.assertIn("Selling Price", csv_wm)
        self.assertIn("Stock Quantity", csv_wm)


if __name__ == "__main__":
    unittest.main()
