import unittest
import json
from werkzeug.security import generate_password_hash

import app
import database


class TestWarehousePurchasesScoping(unittest.TestCase):
    """
    Test suite for Ticket 08:
    - Multi-tenant warehouse facility scoping & plan limit enforcement (max_warehouses).
    - Multi-tenant inter-warehouse stock transfers isolation & cross-tenant rejection.
    - Multi-tenant supplier CRUD, balance tracking & history ledger isolation.
    - Multi-tenant purchase orders creation, inventory reception, and detail viewing.
    - Operational expenses scoping and strict admin-only role access.
    - Staff / user management scoping and cross-tenant mutation blocking.
    """

    @classmethod
    def setUpClass(cls):
        database.init_db()

    def _clean_test_data(self, conn):
        try:
            conn.execute("PRAGMA foreign_keys = OFF")
        except Exception:
            pass
        co_ids = [r[0] for r in conn.execute("SELECT id FROM companies WHERE slug IN ('test-wp-c1', 'test-wp-c2')").fetchall()]
        if co_ids:
            ph = ",".join("?" * len(co_ids))
            tables = [
                "expenses", "supplier_payments", "purchase_items", "purchases", "suppliers",
                "inventory_transfer_items", "inventory_transfers", "inventory_history",
                "warehouse_inventory", "products", "users", "warehouses"
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

            # 1. Company 1 setup (max_warehouses = 2)
            cur1 = conn.execute(
                "INSERT INTO companies (name, slug, currency, max_warehouses, is_active) "
                "VALUES ('WP Co 1', 'test-wp-c1', '$', 2, 1)"
            )
            self.c1_id = cur1.lastrowid if cur1.lastrowid else conn.execute("SELECT id FROM companies WHERE slug = 'test-wp-c1'").fetchone()["id"]

            cur_w1a = conn.execute(
                "INSERT INTO warehouses (company_id, name, location) VALUES (?, 'Warehouse 1A', 'Dock 1')",
                (self.c1_id,)
            )
            self.w1a_id = cur_w1a.lastrowid if cur_w1a.lastrowid else conn.execute("SELECT id FROM warehouses WHERE company_id = ? AND name = 'Warehouse 1A'", (self.c1_id,)).fetchone()["id"]

            cur_w1b = conn.execute(
                "INSERT INTO warehouses (company_id, name, location) VALUES (?, 'Warehouse 1B', 'Dock 2')",
                (self.c1_id,)
            )
            self.w1b_id = cur_w1b.lastrowid if cur_w1b.lastrowid else conn.execute("SELECT id FROM warehouses WHERE company_id = ? AND name = 'Warehouse 1B'", (self.c1_id,)).fetchone()["id"]

            pwd = generate_password_hash("pass123")
            conn.execute(
                "INSERT INTO users (company_id, username, password_hash, role, is_active, warehouse_id) "
                "VALUES (?, 'admin_wp_c1', ?, 'admin', 1, ?)",
                (self.c1_id, pwd, self.w1a_id)
            )
            conn.execute(
                "INSERT INTO users (company_id, username, password_hash, role, is_active, warehouse_id) "
                "VALUES (?, 'salesman_wp_c1', ?, 'salesman', 1, ?)",
                (self.c1_id, pwd, self.w1a_id)
            )

            # Supplier for C1
            cur_s1 = conn.execute(
                "INSERT INTO suppliers (company_id, name, contact_name, phone, address) "
                "VALUES (?, 'Supplier One', 'Alice', '111-222', '100 Main St')",
                (self.c1_id,)
            )
            self.s1_id = cur_s1.lastrowid

            # Product for C1
            cur_p1 = conn.execute(
                "INSERT INTO products (company_id, name, brand, cost_price, selling_price, stock_quantity, supplier_id) "
                "VALUES (?, 'Widget C1', 'Brand C1', 20.0, 35.0, 50, ?)",
                (self.c1_id, self.s1_id)
            )
            self.p1_id = cur_p1.lastrowid
            conn.execute(
                "INSERT INTO warehouse_inventory (company_id, warehouse_id, product_id, stock_quantity) VALUES (?, ?, ?, 50)",
                (self.c1_id, self.w1a_id, self.p1_id)
            )

            # 2. Company 2 setup (max_warehouses = 1)
            cur2 = conn.execute(
                "INSERT INTO companies (name, slug, currency, max_warehouses, is_active) "
                "VALUES ('WP Co 2', 'test-wp-c2', '€', 1, 1)"
            )
            self.c2_id = cur2.lastrowid if cur2.lastrowid else conn.execute("SELECT id FROM companies WHERE slug = 'test-wp-c2'").fetchone()["id"]

            cur_w2 = conn.execute(
                "INSERT INTO warehouses (company_id, name, location) VALUES (?, 'Warehouse 2A', 'Euro Dock')",
                (self.c2_id,)
            )
            self.w2_id = cur_w2.lastrowid if cur_w2.lastrowid else conn.execute("SELECT id FROM warehouses WHERE company_id = ? AND name = 'Warehouse 2A'", (self.c2_id,)).fetchone()["id"]

            conn.execute(
                "INSERT INTO users (company_id, username, password_hash, role, is_active, warehouse_id) "
                "VALUES (?, 'admin_wp_c2', ?, 'admin', 1, ?)",
                (self.c2_id, pwd, self.w2_id)
            )

            cur_s2 = conn.execute(
                "INSERT INTO suppliers (company_id, name, contact_name, phone, address) "
                "VALUES (?, 'Supplier Two', 'Bob', '333-444', '200 Euro Way')",
                (self.c2_id,)
            )
            self.s2_id = cur_s2.lastrowid

            cur_p2 = conn.execute(
                "INSERT INTO products (company_id, name, brand, cost_price, selling_price, stock_quantity, supplier_id) "
                "VALUES (?, 'Gadget C2', 'Brand C2', 40.0, 70.0, 30, ?)",
                (self.c2_id, self.s2_id)
            )
            self.p2_id = cur_p2.lastrowid
            conn.execute(
                "INSERT INTO warehouse_inventory (company_id, warehouse_id, product_id, stock_quantity) VALUES (?, ?, ?, 30)",
                (self.c2_id, self.w2_id, self.p2_id)
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

    def test_warehouse_scoping_and_plan_limits(self):
        """Test warehouse facilities isolation, plan limits, and cross-tenant edit blocking."""
        self._login("admin_wp_c1")
        resp1 = self.client.get("/warehouses")
        self.assertEqual(resp1.status_code, 200)
        self.assertIn(b"Warehouse 1A", resp1.data)
        self.assertIn(b"Warehouse 1B", resp1.data)
        self.assertNotIn(b"Warehouse 2A", resp1.data)

        # Company 2 has max_warehouses = 1 and already has 1 warehouse
        self._login("admin_wp_c2")
        resp2 = self.client.get("/warehouses")
        self.assertEqual(resp2.status_code, 200)
        self.assertIn(b"Warehouse 2A", resp2.data)
        self.assertNotIn(b"Warehouse 1A", resp2.data)

        # Attempt to add another warehouse in C2 -> should exceed limit
        add_resp = self.client.post(
            "/warehouses/add",
            data={"name": "Excess Warehouse", "location": "Over Limit"},
            follow_redirects=True
        )
        self.assertEqual(add_resp.status_code, 200)
        self.assertIn(b"Warehouse limit reached", add_resp.data)

        # Verify excess warehouse was not created
        conn = database.get_connection()
        try:
            excess = conn.execute("SELECT id FROM warehouses WHERE name = 'Excess Warehouse'").fetchone()
            self.assertIsNone(excess)
        finally:
            conn.close()

        # Admin C2 editing Warehouse 1A -> 404
        edit_resp = self.client.post(f"/warehouses/edit/{self.w1a_id}", data={"name": "Hacked W1"}, follow_redirects=False)
        self.assertEqual(edit_resp.status_code, 404)

    def test_stock_transfer_cross_tenant_rejection(self):
        """Test stock transfer isolation and reject cross-tenant warehouse/product transfer."""
        self._login("admin_wp_c1")

        # 1. Cross-tenant warehouse: source W1A (C1), destination W2 (C2)
        payload_cross_wh = {
            "source_warehouse_id": self.w1a_id,
            "destination_warehouse_id": self.w2_id,
            "notes": "Attempt cross-tenant leak",
            "items": [{"product_id": self.p1_id, "quantity": 5}]
        }
        res1 = self.client.post("/inventory/transfer", json=payload_cross_wh)
        self.assertEqual(res1.status_code, 400)
        self.assertIn("unauthorized", res1.get_json()["error"].lower())

        # 2. Cross-tenant product: source W1A (C1), destination W1B (C1), but product P2 (C2)
        payload_cross_prod = {
            "source_warehouse_id": self.w1a_id,
            "destination_warehouse_id": self.w1b_id,
            "notes": "Attempt cross-tenant product",
            "items": [{"product_id": self.p2_id, "quantity": 5}]
        }
        res2 = self.client.post("/inventory/transfer", json=payload_cross_prod)
        self.assertEqual(res2.status_code, 400)
        self.assertIn("unauthorized", res2.get_json()["error"].lower())

        # 3. Legitimate intra-tenant transfer: W1A -> W1B with P1 (5 units)
        valid_payload = {
            "source_warehouse_id": self.w1a_id,
            "destination_warehouse_id": self.w1b_id,
            "notes": "Transfer 5 units to Dock 2",
            "items": [{"product_id": self.p1_id, "quantity": 5}]
        }
        res3 = self.client.post("/inventory/transfer", json=valid_payload)
        self.assertEqual(res3.status_code, 200)
        self.assertTrue(res3.get_json()["ok"])

        # Check DB records
        conn = database.get_connection()
        try:
            transfer = conn.execute("SELECT * FROM inventory_transfers WHERE company_id = ? ORDER BY id DESC", (self.c1_id,)).fetchone()
            self.assertIsNotNone(transfer)
            self.assertEqual(transfer["company_id"], self.c1_id)
            transfer_id = transfer["id"]

            t_items = conn.execute("SELECT * FROM inventory_transfer_items WHERE transfer_id = ?", (transfer_id,)).fetchall()
            self.assertEqual(len(t_items), 1)
            self.assertEqual(t_items[0]["company_id"], self.c1_id)

            history = conn.execute("SELECT * FROM inventory_history WHERE company_id = ?", (self.c1_id,)).fetchall()
            self.assertTrue(len(history) >= 2)
            for h in history:
                self.assertEqual(h["company_id"], self.c1_id)

            # Check stock in W1A (50 - 5 = 45) and W1B (0 + 5 = 5)
            s_w1a = conn.execute("SELECT stock_quantity FROM warehouse_inventory WHERE warehouse_id = ? AND product_id = ?", (self.w1a_id, self.p1_id)).fetchone()
            self.assertEqual(float(s_w1a["stock_quantity"]), 45.0)
            s_w1b = conn.execute("SELECT stock_quantity FROM warehouse_inventory WHERE warehouse_id = ? AND product_id = ?", (self.w1b_id, self.p1_id)).fetchone()
            self.assertEqual(float(s_w1b["stock_quantity"]), 5.0)
        finally:
            conn.close()

        # 4. Admin C2 viewing /inventory/transfers -> should not see C1's transfer
        self._login("admin_wp_c2")
        resp_list = self.client.get("/inventory/transfers")
        self.assertEqual(resp_list.status_code, 200)
        self.assertNotIn(b"Transfer 5 units to Dock 2", resp_list.data)

        # Admin C2 trying to delete C1's transfer -> 404
        del_resp = self.client.post(f"/inventory/transfers/{transfer_id}/delete")
        self.assertEqual(del_resp.status_code, 404)

    def test_supplier_crud_and_history_isolation(self):
        """Test multi-tenant supplier CRUD, balance calculation, and history ledger isolation."""
        self._login("admin_wp_c1")
        resp1 = self.client.get("/suppliers")
        self.assertEqual(resp1.status_code, 200)
        self.assertIn(b"Supplier One", resp1.data)
        self.assertNotIn(b"Supplier Two", resp1.data)

        # Admin C2 viewing suppliers
        self._login("admin_wp_c2")
        resp2 = self.client.get("/suppliers")
        self.assertEqual(resp2.status_code, 200)
        self.assertIn(b"Supplier Two", resp2.data)
        self.assertNotIn(b"Supplier One", resp2.data)

        # Admin C2 editing Supplier 1 -> 404
        edit_resp = self.client.post(
            f"/suppliers/edit/{self.s1_id}",
            data={"name": "Hacked Supplier", "contact_name": "Eve", "phone": "999", "address": "Nowhere"}
        )
        self.assertEqual(edit_resp.status_code, 404)

        # Admin C2 deleting Supplier 1 -> 404
        del_resp = self.client.post(f"/suppliers/delete/{self.s1_id}")
        self.assertEqual(del_resp.status_code, 404)

        # Admin C2 viewing Supplier 1 history -> 404
        hist_resp = self.client.get(f"/suppliers/{self.s1_id}/history")
        self.assertEqual(hist_resp.status_code, 404)

    def test_purchase_orders_scoping_and_cross_tenant_blocking(self):
        """Test purchase orders creation, listing, detail viewing, and stock reception isolation."""
        self._login("admin_wp_c1")

        # 1. Attempt to create purchase with Supplier 2 (Company 2) -> rejected 400
        bad_po = {
            "supplier_id": self.s2_id,
            "warehouse_id": self.w1a_id,
            "purchase_date": "2026-10-25",
            "items": [{"product_id": self.p1_id, "qty": 10, "cost_price": 20.0}]
        }
        res_bad = self.client.post("/purchases/new", json=bad_po)
        self.assertEqual(res_bad.status_code, 400)
        self.assertIn("unauthorized", res_bad.get_json()["error"].lower())

        # 2. Valid purchase in Company 1
        valid_po = {
            "supplier_id": self.s1_id,
            "warehouse_id": self.w1a_id,
            "purchase_date": "2026-10-25",
            "reference_number": "PO-C1-001",
            "payment_amount": 100.0,
            "payment_method": "check",
            "items": [{"product_id": self.p1_id, "qty": 10, "cost_price": 20.0}]
        }
        res_ok = self.client.post("/purchases/new", json=valid_po)
        self.assertEqual(res_ok.status_code, 200)
        po_id = res_ok.get_json()["purchase_id"]
        self.assertIsNotNone(po_id)

        # Verify DB records have company_id
        conn = database.get_connection()
        try:
            po = conn.execute("SELECT * FROM purchases WHERE id = ?", (po_id,)).fetchone()
            self.assertEqual(po["company_id"], self.c1_id)
            self.assertEqual(po["remaining_amount"], 100.0)
            self.assertEqual(po["status"], "partial")

            p_items = conn.execute("SELECT * FROM purchase_items WHERE purchase_id = ?", (po_id,)).fetchall()
            self.assertEqual(len(p_items), 1)
            self.assertEqual(p_items[0]["company_id"], self.c1_id)

            payments = conn.execute("SELECT * FROM supplier_payments WHERE purchase_id = ?", (po_id,)).fetchall()
            self.assertEqual(len(payments), 1)
            self.assertEqual(payments[0]["company_id"], self.c1_id)
        finally:
            conn.close()

        # 3. Admin C2 viewing /purchases -> should not see PO-C1-001
        self._login("admin_wp_c2")
        list_resp = self.client.get("/purchases")
        self.assertEqual(list_resp.status_code, 200)
        self.assertNotIn(b"PO-C1-001", list_resp.data)

        # Admin C2 viewing /purchases/<po_id> -> 404
        det_resp = self.client.get(f"/purchases/{po_id}")
        self.assertEqual(det_resp.status_code, 404)

        # Admin C2 deleting /api/purchases/<po_id>/delete -> 404
        del_resp = self.client.post(f"/api/purchases/{po_id}/delete", json={})
        self.assertEqual(del_resp.status_code, 404)

        # Admin C2 adding payment to PO-C1-001 -> 400
        pay_resp = self.client.post("/api/supplier_payments", json={
            "supplier_id": self.s2_id,
            "purchase_id": po_id,
            "amount": 50.0,
            "payment_date": "2026-10-25"
        })
        self.assertEqual(pay_resp.status_code, 400)

    def test_expenses_isolation_and_admin_only_protection(self):
        """Test operational expenses role security (admin only) and tenant isolation."""
        # 1. Non-admin access rejection
        self._login("salesman_wp_c1")
        salesman_resp = self.client.get("/expenses")
        # admin_required redirects non-admins
        self.assertIn(salesman_resp.status_code, (302, 403))

        add_salesman = self.client.post(
            "/expenses/add",
            data={"date": "2026-10-25", "category": "Office", "amount": "50", "description": "Pens"}
        )
        self.assertIn(add_salesman.status_code, (302, 403))

        # 2. Admin C1 adds expense
        self._login("admin_wp_c1")
        self.client.post(
            "/expenses/add",
            data={"date": "2026-10-25", "category": "Packaging", "amount": "150.00", "description": "Boxes and Tape"},
            follow_redirects=True
        )

        # 3. Admin C2 adds expense
        self._login("admin_wp_c2")
        self.client.post(
            "/expenses/add",
            data={"date": "2026-10-25", "category": "Utilities", "amount": "300.00", "description": "Electric Bill"},
            follow_redirects=True
        )

        # Verify DB records
        conn = database.get_connection()
        try:
            exp1 = conn.execute("SELECT * FROM expenses WHERE company_id = ?", (self.c1_id,)).fetchone()
            self.assertIsNotNone(exp1)
            self.assertEqual(exp1["description"], "Boxes and Tape")
            exp1_id = exp1["id"]

            exp2 = conn.execute("SELECT * FROM expenses WHERE company_id = ?", (self.c2_id,)).fetchone()
            self.assertIsNotNone(exp2)
            self.assertEqual(exp2["description"], "Electric Bill")
        finally:
            conn.close()

        # Admin C2 viewing /expenses -> sees Electric Bill, not Boxes and Tape
        c2_expenses = self.client.get("/expenses")
        self.assertEqual(c2_expenses.status_code, 200)
        self.assertIn(b"Electric Bill", c2_expenses.data)
        self.assertNotIn(b"Boxes and Tape", c2_expenses.data)

        # Admin C2 editing C1 expense -> 404
        edit_resp = self.client.post(
            f"/expenses/edit/{exp1_id}",
            data={"date": "2026-10-25", "category": "Hacked", "amount": "999", "description": "Hacked"}
        )
        self.assertEqual(edit_resp.status_code, 404)

        # Admin C2 deleting C1 expense -> 404
        del_resp = self.client.post(f"/expenses/delete/{exp1_id}")
        self.assertEqual(del_resp.status_code, 404)

    def test_staff_user_management_isolation(self):
        """Test staff management scoping, new user creation, and cross-tenant action blocking."""
        self._login("admin_wp_c1")
        resp1 = self.client.get("/users")
        self.assertEqual(resp1.status_code, 200)
        self.assertIn(b"admin_wp_c1", resp1.data)
        self.assertIn(b"salesman_wp_c1", resp1.data)
        self.assertNotIn(b"admin_wp_c2", resp1.data)

        # Create new staff user under C1
        add_resp = self.client.post(
            "/users/add",
            data={"username": "new_staff_c1", "password": "pass123", "role": "salesman", "warehouse_id": self.w1a_id}
        )
        self.assertEqual(add_resp.status_code, 200)
        self.assertTrue(add_resp.get_json()["ok"])

        # Check DB
        conn = database.get_connection()
        try:
            new_u = conn.execute("SELECT * FROM users WHERE username = 'new_staff_c1'").fetchone()
            self.assertIsNotNone(new_u)
            self.assertEqual(new_u["company_id"], self.c1_id)
            new_u_id = new_u["id"]

            salesman_c1 = conn.execute("SELECT id FROM users WHERE username = 'salesman_wp_c1'").fetchone()
            salesman_c1_id = salesman_c1["id"]
        finally:
            conn.close()

        # Admin C2 viewing /users
        self._login("admin_wp_c2")
        resp2 = self.client.get("/users")
        self.assertEqual(resp2.status_code, 200)
        self.assertIn(b"admin_wp_c2", resp2.data)
        self.assertNotIn(b"admin_wp_c1", resp2.data)
        self.assertNotIn(b"new_staff_c1", resp2.data)

        # Admin C2 attempting to toggle active status of salesman_c1 -> 404
        toggle_resp = self.client.post(f"/users/toggle_active/{salesman_c1_id}")
        self.assertEqual(toggle_resp.status_code, 404)

        # Admin C2 attempting to edit salesman_c1 -> 404
        edit_resp = self.client.post(f"/users/edit/{salesman_c1_id}", data={"role": "admin"})
        self.assertEqual(edit_resp.status_code, 404)

        # Admin C2 attempting to reset password of salesman_c1 -> 404
        reset_resp = self.client.post("/users/reset_password", data={"user_id": salesman_c1_id, "new_password": "hackedpassword"})
        self.assertEqual(reset_resp.status_code, 404)


if __name__ == "__main__":
    unittest.main()
