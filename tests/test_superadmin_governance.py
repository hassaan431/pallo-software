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
        if not database.is_postgres_configured():
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
            
            conn.execute("DELETE FROM users WHERE username IN ('test_superadmin_user', 'new_team_member')")
            conn.commit()
            try:
                conn.execute("PRAGMA foreign_keys = ON")
            except Exception:
                pass
        else:
            try:
                co_ids = [r[0] for r in conn.execute("SELECT id FROM companies WHERE slug IN ('test-sa-c1', 'test-sa-c2')").fetchall()]
                if co_ids:
                    ph = ",".join(["?"] * len(co_ids))
                    tables = ["users"]
                    for tbl in tables:
                        try:
                            conn.execute(f"DELETE FROM {tbl} WHERE company_id IN ({ph})", co_ids)
                        except Exception:
                            try:
                                conn.rollback()
                            except Exception:
                                pass
                    try:
                        conn.execute(f"DELETE FROM companies WHERE id IN ({ph})", co_ids)
                    except Exception:
                        try:
                            conn.rollback()
                        except Exception:
                            pass
                try:
                    conn.execute("DELETE FROM users WHERE username IN ('test_superadmin_user', 'new_team_member')")
                except Exception:
                    try:
                        conn.rollback()
                    except Exception:
                        pass
                conn.commit()
            except Exception:
                try:
                    conn.rollback()
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
                VALUES ('SuperAdmin Test Co 1', 'test-sa-c1', '$', 'SAT1-', TRUE, 3)
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
            self.assertIn(co["is_active"], (0, False, "0"))
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
            self.assertIn(co["is_active"], (1, True, "1"))
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

    def test_superadmin_tenant_switcher(self):
        """SuperAdmin can switch tenant context on the fly via /superadmin/switch-tenant/<id>."""
        self._login("test_superadmin_user", "superpass123")

        # 1. Switch to Tenant Company 1
        res = self.client.get(f"/superadmin/switch-tenant/{self.c1_id}", follow_redirects=True)
        self.assertEqual(res.status_code, 200)
        self.assertIn(b"Switched active workspace view to", res.data)
        self.assertIn(b"SuperAdmin Test Co 1", res.data)

        with self.client.session_transaction() as sess:
            self.assertEqual(sess.get("active_company_id"), self.c1_id)

        # 2. Access Settings Hub while switched -> company is SuperAdmin Test Co 1
        res = self.client.get("/settings?tab=company")
        self.assertEqual(res.status_code, 200)
        self.assertIn(b"SuperAdmin Test Co 1", res.data)

        # 3. Clear tenant switch -> returns to platform overview
        res = self.client.get("/superadmin/switch-tenant/clear", follow_redirects=True)
        self.assertEqual(res.status_code, 200)
        self.assertIn(b"Reset workspace view to platform default", res.data)

        with self.client.session_transaction() as sess:
            self.assertIsNone(sess.get("active_company_id"))

    def test_settings_inline_users_management(self):
        """Test inline user management from Settings Hub Tab 2."""
        self._login("test_superadmin_user", "superpass123")

        # 1. Switch to Tenant Company
        self.client.get(f"/superadmin/switch-tenant/{self.c1_id}")

        # 2. View Team & Users tab in Settings Hub
        res = self.client.get("/settings?tab=users")
        self.assertEqual(res.status_code, 200)
        self.assertIn(b"Team & User Accounts", res.data)
        self.assertIn(b"Add Team Member", res.data)
        self.assertIn(b"test_sa_regular_admin", res.data)

        # 3. Add a new team member via /users/add
        res = self.client.post("/users/add", data={
            "username": "new_team_member",
            "password": "securepass123",
            "role": "salesman"
        })
        self.assertEqual(res.status_code, 200)
        data = res.get_json()
        self.assertTrue(data.get("ok"))

        # Verify added to database under switched company
        conn = database.get_connection()
        try:
            u = conn.execute("SELECT id, username, company_id, is_active FROM users WHERE username = 'new_team_member'").fetchone()
            self.assertIsNotNone(u)
            self.assertEqual(u["company_id"], self.c1_id)
            user_id = u["id"]
        finally:
            conn.close()

        # 4. Toggle active status with Referer header pointing to settings?tab=users
        res = self.client.post(
            f"/users/toggle_active/{user_id}",
            headers={"Referer": "http://localhost/settings?tab=users"},
            follow_redirects=True
        )
        self.assertEqual(res.status_code, 200)
        self.assertIn(b"suspended successfully", res.data)

        # 5. Edit user role
        res = self.client.post(
            f"/users/edit/{user_id}",
            data={"role": "admin"},
            headers={"Referer": "http://localhost/settings?tab=users"},
            follow_redirects=True
        )
        self.assertEqual(res.status_code, 200)
        self.assertIn(b"updated successfully", res.data)


if __name__ == "__main__":
    unittest.main()

