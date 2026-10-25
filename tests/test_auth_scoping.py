import unittest
from unittest.mock import MagicMock, patch
from werkzeug.security import generate_password_hash

import app as flask_app
from database import get_company


class TestAuthAndSessionScoping(unittest.TestCase):
    def setUp(self):
        flask_app.app.config["TESTING"] = True
        flask_app.app.config["WTF_CSRF_ENABLED"] = False
        flask_app.app.secret_key = "test-secret"
        self.client = flask_app.app.test_client()

    def test_user_model_company_scoping(self):
        user = flask_app.User(
            db_id=10,
            username="testuser",
            role="admin",
            warehouse_id=2,
            company_id=5,
        )
        self.assertEqual(user.id, 10)
        self.assertEqual(user.username, "testuser")
        self.assertEqual(user.role, "admin")
        self.assertEqual(user.warehouse_id, 2)
        self.assertEqual(user.company_id, 5)

    def test_get_company_default_company_1(self):
        comp = get_company(1)
        self.assertIsNotNone(comp)
        self.assertEqual(comp["id"], 1)
        self.assertEqual(comp["name"], "AK Distributors LLC")
        self.assertEqual(comp["slug"], "ak-distributors")
        self.assertTrue(comp["is_active"])

    def test_load_user_resolves_company_and_active_status(self):
        mock_user_row = {
            "id": 1,
            "username": "admin",
            "role": "admin",
            "is_active": 1,
            "warehouse_id": 1,
            "company_id": 1,
        }
        with patch("app.get_user_by_id", return_value=mock_user_row):
            loaded = flask_app.load_user(1)
            self.assertIsNotNone(loaded)
            self.assertEqual(loaded.company_id, 1)
            self.assertEqual(loaded.username, "admin")

    def test_load_user_rejects_disabled_user(self):
        mock_user_row = {
            "id": 2,
            "username": "disabled_user",
            "role": "salesman",
            "is_active": 0,
            "company_id": 1,
        }
        with patch("app.get_user_by_id", return_value=mock_user_row):
            self.assertIsNone(flask_app.load_user(2))

    def test_load_user_enforces_company_soft_deactivation(self):
        mock_user_row = {
            "id": 3,
            "username": "tenant_staff",
            "role": "admin",
            "is_active": 1,
            "company_id": 2,
        }
        suspended_company = {
            "id": 2,
            "name": "Paused Tenant",
            "slug": "paused-tenant",
            "is_active": False,
        }
        with patch("app.get_user_by_id", return_value=mock_user_row), \
             patch("app.get_company", return_value=suspended_company):
            # User should be blocked due to company deactivation
            self.assertIsNone(flask_app.load_user(3))

    def test_load_user_superadmin_bypasses_company_deactivation(self):
        mock_superadmin_row = {
            "id": 99,
            "username": "superadmin",
            "role": "superadmin",
            "is_active": 1,
            "company_id": None,
        }
        with patch("app.get_user_by_id", return_value=mock_superadmin_row):
            loaded = flask_app.load_user(99)
            self.assertIsNotNone(loaded)
            self.assertEqual(loaded.role, "superadmin")

    def test_context_processor_injects_company_and_brand(self):
        with flask_app.app.test_request_context("/"):
            ctx = flask_app.inject_pallo_context()
            self.assertIn("current_company", ctx)
            self.assertIn("app_name", ctx)
            self.assertEqual(ctx["app_name"], "Pallo")
            self.assertIn("is_superadmin", ctx)
            self.assertEqual(ctx["current_company"]["id"], 1)

    def test_login_rejects_deactivated_company(self):
        password_hash = generate_password_hash("secret123", method="pbkdf2:sha256")
        mock_user_row = {
            "id": 5,
            "username": "tenant_owner",
            "password_hash": password_hash,
            "role": "admin",
            "is_active": 1,
            "company_id": 3,
        }
        suspended_company = {
            "id": 3,
            "name": "Suspended Corp",
            "is_active": False,
        }

        with patch("app.get_user_by_username", return_value=mock_user_row), \
             patch("app.get_company", return_value=suspended_company):
            resp = self.client.post(
                "/login",
                data={"username": "tenant_owner", "password": "secret123"},
            )
            self.assertEqual(resp.status_code, 200)
            self.assertIn(b"Your company account has been paused or suspended", resp.data)


if __name__ == "__main__":
    unittest.main()
