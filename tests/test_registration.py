import unittest
from unittest.mock import MagicMock, patch
import app as flask_app
import database


class TestCompanyRegistration(unittest.TestCase):
    def setUp(self):
        flask_app.app.config["TESTING"] = True
        flask_app.app.config["WTF_CSRF_ENABLED"] = False
        flask_app.app.secret_key = "test-secret"
        self.client = flask_app.app.test_client()

    def test_generate_company_slug(self):
        with patch("database.get_connection") as mock_conn:
            mock_cur = MagicMock()
            mock_conn.return_value.cursor.return_value = mock_cur
            # First slug check finds None (available)
            mock_cur.fetchone.return_value = None

            slug = database.generate_company_slug("Apex Global Foods LLC")
            self.assertEqual(slug, "apex-global-foods-llc")

    def test_generate_company_slug_collision_resolution(self):
        with patch("database.get_connection") as mock_conn:
            mock_cur = MagicMock()
            mock_conn.return_value.cursor.return_value = mock_cur
            # First slug check finds existing row, second check finds None
            mock_cur.fetchone.side_effect = [{"id": 1}, None]

            slug = database.generate_company_slug("Apex Global")
            self.assertEqual(slug, "apex-global-2")

    def test_get_register_page(self):
        resp = self.client.get("/register")
        self.assertEqual(resp.status_code, 200)
        self.assertIn(b"Start your business on Pallo", resp.data)
        self.assertIn(b"Company / Business Name", resp.data)

    def test_register_validation_short_company_name(self):
        resp = self.client.post(
            "/register",
            data={
                "company_name": "A",
                "username": "validuser",
                "password": "password123",
                "confirm_password": "password123",
                "currency": "$",
            },
        )
        self.assertEqual(resp.status_code, 200)
        self.assertIn(b"Company name must be at least 2 characters", resp.data)

    def test_register_validation_duplicate_username(self):
        with patch("app.get_user_by_username", return_value={"id": 1, "username": "admin"}):
            resp = self.client.post(
                "/register",
                data={
                    "company_name": "Apex Supplies",
                    "username": "admin",
                    "password": "password123",
                    "confirm_password": "password123",
                    "currency": "$",
                },
            )
            self.assertEqual(resp.status_code, 200)
            self.assertIn(b"username is already taken", resp.data)

    def test_register_validation_mismatched_password(self):
        with patch("app.get_user_by_username", return_value=None):
            resp = self.client.post(
                "/register",
                data={
                    "company_name": "Apex Supplies",
                    "username": "apexadmin",
                    "password": "password123",
                    "confirm_password": "mismatchpassword",
                    "currency": "$",
                },
            )
            self.assertEqual(resp.status_code, 200)
            self.assertIn(b"Passwords do not match", resp.data)

    def test_register_success_flow(self):
        with patch("app.get_user_by_username", return_value=None), \
             patch("app.register_company_with_admin", return_value=(2, 10)) as mock_reg:
            resp = self.client.post(
                "/register",
                data={
                    "company_name": "Apex Supplies LLC",
                    "username": "apexowner",
                    "password": "securepassword123",
                    "confirm_password": "securepassword123",
                    "currency": "$",
                },
            )
            # Should redirect to dashboard upon successful registration and auto-login
            self.assertEqual(resp.status_code, 302)
            self.assertIn("/dashboard", resp.headers["Location"])
            mock_reg.assert_called_once()
            call_kwargs = mock_reg.call_args[1]
            self.assertEqual(call_kwargs["company_name"], "Apex Supplies LLC")
            self.assertEqual(call_kwargs["admin_username"], "apexowner")
            self.assertEqual(call_kwargs["currency"], "$")


if __name__ == "__main__":
    unittest.main()
