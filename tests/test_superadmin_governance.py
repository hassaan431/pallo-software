import unittest
from werkzeug.security import generate_password_hash

import app
import database


class TestSuperAdminPlatformGovernance(unittest.TestCase):
    """
    Test suite for Ticket 10:
    - SuperAdmin role access gate (@superadmin_required).
    - Platform governance dashboard (/superadmin) metric aggregation.
    - 1-click tenant soft-deactivation toggle (/superadmin/company/<id>/toggle_status).
    - Master Company 1 protection against deactivation.
    - Tenant login interception upon suspension (ADR 0004).
    - Plan capacity limit updates (max_warehouses).
    """

    @classmethod
    def setUpClass(cls):
        database.init_db()

    def _clean_test_data(self, conn):
        try:
            conn.execute("PRAGMA foreign_keys = OFF")
        except Exception:
            pass
        co_ids = [r[0] for r in conn.execute("SELECT id FROM companies WHERE slug IN ('test-sa-c1', 'test-sa-c2')").fetchall()]
        if co_ids:
            ph = ",".join("?" * len(co_ids))
            tables = ["users", "companies"]
            for tbl in tables:
                chk = conn.execute("SELECT name FROM sqlite_master WHERE type='table' AND name=?", (tbl,)).fetchone()
                if chk:
                    cols = [r[1] for r in conn.execute(f"PRAGMA table_info({tbl})").fetchall()]
                    if "company_id" in cols:
                        conn.execute(f"DELETE FROM {tbl} WHERE company_id IN ({ph})", co_ids)
            conn.execute(f"DELETE FROM companies WHERE id IN ({ph})", co_ids)
        
        # Clean superadmin user if created
        conn.execute("DELETE FROM users WHERE username = 'test_superadmin_user'")
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

            # 1. Create a SuperAdmin user (company_id=1, role='superadmin')
            conn.execute(
                """
                INSERT INTO users (username, password_hash, role, company_id)
                VALUES ('test_superadmin_user', ?, 'superadmin', 1)
                """,
                (generate_password_hash("superpass123", method="pbkdf2:sha256"),)
            )

            # 2. Create Tenant Company 1 (test-sa-c1)
            conn.execute(
                """
                INSERT INTO companies (name, slug, currency, invoice_prefix, is_active, max_warehouses)
                VALUES ('SuperAdmin Test Co 1', 'test-sa-c1', '$', 'SAT1-', 1, 3)
                """
            )
            self.c1_id = conn.execute("SELECT id FROM companies WHERE slug = 'test-sa-c1'").fetchone()[0]

            # Tenant regular admin
            conn.execute(
                """
                INSERT INTO users (username, password_hash, role, company_id)
                VALUES ('test_sa_regular_admin', ?, 'admin', ?)
                """,
                (generate_password_hash("pass123", method="pbkdf2:sha256"), self.c1_id)
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

    def _login(self, username, password="password"):
        self.client.get("/logout")
        with self.client.session_transaction() as sess:
            sess.clear()
        return self.client.post("/login", data={"username": username, "password": password}, follow_redirects=True)

    def test_superadmin_access_control(self):
        """Only superadmin role is permitted into /superadmin console."""
        # 1. Unauthenticated -> login redirect
        res = self.client.get("/superadmin")
        self.assertEqual(res.status_code, 302)
        self.assertIn("/login", res.headers.get("Location", ""))

        # 2. Regular Company Admin -> redirected away to dashboard
        self._login("test_sa_regular_admin", "pass123")
        res = self.client.get("/superadmin")
        self.assertEqual(res.status_code, 302)
        self.assertIn("/dashboard", res.headers.get("Location", ""))

        # 3. SuperAdmin user -> gets 200 OK
        self._login("test_superadmin_user", "superpass123")
        res = self.client.get("/superadmin")
        self.assertEqual(res.status_code, 200)
        self.assertIn(b"Platform Governance", res.data)
        self.assertIn(b"Registered Tenants", res.data)
        self.assertIn(b"SuperAdmin Test Co 1", res.data)

    def test_master_company_1_protected_from_deactivation(self):
        """Company 1 (AK Distributors LLC) cannot be paused or deactivated."""
        self._login("test_superadmin_user", "superpass123")

        res = self.client.post("/superadmin/company/1/toggle_status", follow_redirects=True)
        self.assertEqual(res.status_code, 200)
        self.assertIn(b"Master company (AK Distributors LLC) cannot be deactivated", res.data)

        # Verify Company 1 remains active in database
        conn = database.get_connection()
        try:
            co1 = conn.execute("SELECT is_active FROM companies WHERE id = 1").fetchone()
            self.assertIn(co1["is_active"], (1, True, "1"))
        finally:
            conn.close()

    def test_tenant_soft_deactivation_and_login_interception(self):
        """Suspending a company intercepts its user logins immediately per ADR 0004."""
        self._login("test_superadmin_user", "superpass123")

        # 1. Suspend Tenant Company
        res = self.client.post(f"/superadmin/company/{self.c1_id}/toggle_status", follow_redirects=True)
        self.assertEqual(res.status_code, 200)
        self.assertIn(b"deactivated successfully", res.data)

        # Verify DB is_active = 0
        conn = database.get_connection()
        try:
            co = conn.execute("SELECT is_active FROM companies WHERE id = ?", (self.c1_id,)).fetchone()
            self.assertEqual(int(co["is_active"]), 0)
        finally:
            conn.close()

        # 2. Attempt login by tenant user -> blocked with suspended notice
        res = self._login("test_sa_regular_admin", "pass123")
        self.assertIn(b"company account has been paused or suspended", res.data)

        # 3. Reactivate company
        self._login("test_superadmin_user", "superpass123")
        res = self.client.post(f"/superadmin/company/{self.c1_id}/toggle_status", follow_redirects=True)
        self.assertEqual(res.status_code, 200)
        self.assertIn(b"reactivated successfully", res.data)

        # Verify DB is_active = 1
        conn = database.get_connection()
        try:
            co = conn.execute("SELECT is_active FROM companies WHERE id = ?", (self.c1_id,)).fetchone()
            self.assertEqual(int(co["is_active"]), 1)
        finally:
            conn.close()

        # 4. Tenant user can now log in successfully
        res = self._login("test_sa_regular_admin", "pass123")
        self.assertNotIn(b"paused or suspended", res.data)
        self.assertEqual(res.status_code, 200)

    def test_superadmin_update_plan_capacity(self):
        """SuperAdmin can update the warehouse capacity limit for tenants."""
        self._login("test_superadmin_user", "superpass123")

        res = self.client.post(
            f"/superadmin/company/{self.c1_id}/update_plan",
            data={"max_warehouses": "12"},
            follow_redirects=True
        )
        self.assertEqual(res.status_code, 200)
        self.assertIn(b"Tenant plan capacity updated successfully", res.data)

        conn = database.get_connection()
        try:
            co = conn.execute("SELECT max_warehouses FROM companies WHERE id = ?", (self.c1_id,)).fetchone()
            self.assertEqual(co["max_warehouses"], 12)
        finally:
            conn.close()


if __name__ == "__main__":
    unittest.main()
