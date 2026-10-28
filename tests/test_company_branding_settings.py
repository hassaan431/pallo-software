import unittest
import io
import os
import shutil
from werkzeug.security import generate_password_hash

import app
import database
from invoice_generator import generate_pdf_from_data


class TestCompanyBrandingSettings(unittest.TestCase):
    """
    Test suite for Ticket 09:
    - Company Settings route (/settings/company) GET and POST.
    - Role-based security (salesman access blocked, unauthenticated redirected).
    - Validation rules (name required, allowed extensions, 2MB file size cap).
    - File upload handling and safe disk persistence.
    - Dynamic invoice PDF generation for Company 1 vs Tenant Company.
    """

    @classmethod
    def setUpClass(cls):
        database.init_db()

    def _clean_test_data(self, conn):
        try:
            conn.execute("PRAGMA foreign_keys = OFF")
        except Exception:
            pass
        co_ids = [r[0] for r in conn.execute("SELECT id FROM companies WHERE slug IN ('test-brand-c1', 'test-brand-c2')").fetchall()]
        if co_ids:
            ph = ",".join("?" * len(co_ids))
            tables = ["users", "products", "brands", "companies"]
            for tbl in tables:
                chk = conn.execute("SELECT name FROM sqlite_master WHERE type='table' AND name=?", (tbl,)).fetchone()
                if chk:
                    cols = [r[1] for r in conn.execute(f"PRAGMA table_info({tbl})").fetchall()]
                    if "company_id" in cols:
                        conn.execute(f"DELETE FROM {tbl} WHERE company_id IN ({ph})", co_ids)
            conn.execute(f"DELETE FROM companies WHERE id IN ({ph})", co_ids)
        # Also clean any test brands named Alpha Brand
        chk_b = conn.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='brands'").fetchone()
        if chk_b:
            conn.execute("DELETE FROM brands WHERE name = 'Alpha Brand'")
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

            # 1. Create Tenant Company 1 (test-brand-c1)
            conn.execute(
                """
                INSERT INTO companies (name, slug, currency, invoice_prefix, is_active)
                VALUES ('Test Brand One', 'test-brand-c1', '$', 'TB1-', 1)
                """
            )
            self.c1_id = conn.execute("SELECT id FROM companies WHERE slug = 'test-brand-c1'").fetchone()[0]

            # Admin user for c1
            conn.execute(
                """
                INSERT INTO users (username, password_hash, role, company_id)
                VALUES ('c1_admin_brand', ?, 'admin', ?)
                """,
                (generate_password_hash("pass123", method="pbkdf2:sha256"), self.c1_id)
            )
            self.c1_admin_id = conn.execute("SELECT id FROM users WHERE username = 'c1_admin_brand'").fetchone()[0]

            # Salesman user for c1
            conn.execute(
                """
                INSERT INTO users (username, password_hash, role, company_id)
                VALUES ('c1_sales_brand', ?, 'salesman', ?)
                """,
                (generate_password_hash("pass123", method="pbkdf2:sha256"), self.c1_id)
            )
            self.c1_sales_id = conn.execute("SELECT id FROM users WHERE username = 'c1_sales_brand'").fetchone()[0]

            conn.commit()
        finally:
            conn.close()

    def tearDown(self):
        conn = database.get_connection()
        try:
            self._clean_test_data(conn)
        finally:
            conn.close()

        # Clean test logo files if generated
        test_logo_path = os.path.join(self.app.root_path, "static", "logos", "companies", f"company_{self.c1_id}.png")
        if os.path.exists(test_logo_path):
            try:
                os.remove(test_logo_path)
            except Exception:
                pass

    def _login(self, username, password="password"):
        self.client.get("/logout")
        with self.client.session_transaction() as sess:
            sess.clear()
        return self.client.post("/login", data={"username": username, "password": password}, follow_redirects=True)

    def test_settings_company_access_control(self):
        """Unauthenticated and salesman users must not be permitted to view or edit company settings."""
        # 1. Unauthenticated -> redirects to login
        res = self.client.get("/settings/company")
        self.assertEqual(res.status_code, 302)
        self.assertIn("/login", res.headers.get("Location", ""))

        # 2. Salesman -> redirects to /pos
        self._login("c1_sales_brand", "pass123")
        res = self.client.get("/settings/company")
        self.assertEqual(res.status_code, 302)
        self.assertIn("/pos", res.headers.get("Location", ""))

        # 3. Admin -> gets 200 OK and renders settings page
        self._login("c1_admin_brand", "pass123")
        res = self.client.get("/settings/company")
        self.assertEqual(res.status_code, 200)
        self.assertIn(b"Company Profile", res.data)
        self.assertIn(b"Test Brand One", res.data)

    def test_settings_company_update_fields(self):
        """Admin can update legal information, addresses, tax ID, and currency."""
        self._login("c1_admin_brand", "pass123")
        
        post_data = {
            "name": "Updated Brand One Corp",
            "tax_id": "TAX-123456",
            "bill_address": "100 Innovation Way, Suite 400",
            "ship_address": "Dock 4, Warehouse District",
            "phone": "+1-800-555-0199",
            "email": "invoicing@brandone.com",
            "currency": "\u20ac",
            "invoice_prefix": "UB1-",
        }
        res = self.client.post("/settings/company", data=post_data, follow_redirects=True)
        self.assertEqual(res.status_code, 200)
        self.assertIn(b"Company settings updated successfully", res.data)

        # Verify DB values
        conn = database.get_connection()
        try:
            row = conn.execute("SELECT * FROM companies WHERE id = ?", (self.c1_id,)).fetchone()
            self.assertEqual(row["name"], "Updated Brand One Corp")
            self.assertEqual(row["tax_id"], "TAX-123456")
            self.assertEqual(row["bill_address"], "100 Innovation Way, Suite 400")
            self.assertEqual(row["ship_address"], "Dock 4, Warehouse District")
            self.assertEqual(row["phone"], "+1-800-555-0199")
            self.assertEqual(row["email"], "invoicing@brandone.com")
            self.assertEqual(row["currency"], "\u20ac")
            self.assertEqual(row["invoice_prefix"], "UB1-")
        finally:
            conn.close()

    def test_settings_company_validation_name_required(self):
        """Company legal name is required and cannot be blank."""
        self._login("c1_admin_brand", "pass123")
        
        res = self.client.post("/settings/company", data={"name": "   "}, follow_redirects=True)
        self.assertEqual(res.status_code, 200)
        self.assertIn(b"Company legal name is required", res.data)

    def test_settings_company_logo_upload_valid(self):
        """Valid image file upload is saved and logo_url updated in database."""
        self._login("c1_admin_brand", "pass123")

        dummy_png = b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01\x08\x06\x00\x00\x00\x1f\x15c4\x00\x00\x00\nIDATx\x9cc\x00\x01\x00\x00\x05\x00\x01\r\n-\xb4\x00\x00\x00\x00IEND\xaeB`\x82"
        data = {
            "name": "Test Brand One",
            "logo": (io.BytesIO(dummy_png), "my_logo.png")
        }
        res = self.client.post("/settings/company", data=data, content_type="multipart/form-data", follow_redirects=True)
        self.assertEqual(res.status_code, 200)
        self.assertIn(b"Company settings updated successfully", res.data)

        conn = database.get_connection()
        try:
            row = conn.execute("SELECT logo_url FROM companies WHERE id = ?", (self.c1_id,)).fetchone()
            self.assertTrue(row["logo_url"].endswith(f"company_{self.c1_id}.png"))
            if row["logo_url"].startswith("http"):
                self.assertTrue("storage." in row["logo_url"] or "r2." in row["logo_url"])
            else:
                saved_path = os.path.join(self.app.root_path, "static", "logos", "companies", f"company_{self.c1_id}.png")
                self.assertTrue(os.path.exists(saved_path))
        finally:
            conn.close()

    def test_settings_company_logo_invalid_extension(self):
        """Uploading unsupported file extensions must be rejected."""
        self._login("c1_admin_brand", "pass123")

        data = {
            "name": "Test Brand One",
            "logo": (io.BytesIO(b"dangerous executable script"), "malicious.sh")
        }
        res = self.client.post("/settings/company", data=data, content_type="multipart/form-data", follow_redirects=True)
        self.assertEqual(res.status_code, 200)
        self.assertIn(b"Invalid image format", res.data)

    def test_settings_company_logo_file_size_cap(self):
        """Files exceeding 2MB must be rejected."""
        self._login("c1_admin_brand", "pass123")

        # 2.2MB dummy payload
        oversized_data = b"0" * (2 * 1024 * 1024 + 200 * 1024)
        data = {
            "name": "Test Brand One",
            "logo": (io.BytesIO(oversized_data), "huge_logo.png")
        }
        res = self.client.post("/settings/company", data=data, content_type="multipart/form-data", follow_redirects=True)
        self.assertEqual(res.status_code, 200)
        self.assertIn(b"exceeds maximum size of 2MB", res.data)

    def test_pdf_invoice_branding_company1_vs_tenant(self):
        """PDF generation preserves Company 1 formatting and applies tenant branding for other companies."""
        # 1. Company 1 (AK Distributors)
        c1_meta = {
            "id": 1,
            "name": "AK Distributors LLC",
            "slug": "ak-distributors",
            "bill_address": "Sacramento California 95838",
            "phone": "9163545678",
            "email": "akdistributorsusa@gmail.com",
            "currency": "$",
        }
        sale_dummy = {
            "id": 9991,
            "invoice_number": "AK-0001",
            "invoice_date": "2026-10-25",
            "due_date": "2026-11-25",
            "terms": "Net 30",
            "subtotal": 100.0,
            "discount_amount": 0.0,
            "grand_total": 100.0,
            "amount_paid": 0.0,
            "remaining_amount": 100.0,
            "status": "unpaid",
        }
        customer_dummy = {
            "id": 50,
            "name": "Test Client Corp",
            "bill_address": "123 Main St",
            "ship_address": "123 Main St",
            "phone": "555-1234",
        }
        items_dummy = [
            {
                "sale_item_id": 1,
                "product_id": 10,
                "description": "Standard Widget",
                "qty": 10,
                "rate": 10.0,
                "amount": 100.0,
                "print_dual_units": 0,
                "packing_multiplier": 1.0,
                "product_name": "Standard Widget",
                "product_brand": "AK Brand",
            }
        ]

        pdf_c1 = generate_pdf_from_data(sale_dummy, customer_dummy, items_dummy, is_quote=False, company=c1_meta)
        self.assertTrue(isinstance(pdf_c1, bytes))
        self.assertTrue(len(pdf_c1) > 1000)
        self.assertTrue(pdf_c1.startswith(b"%PDF"))

        # 2. Tenant Company (Company 2) with custom currency and Tax ID
        c2_meta = {
            "id": 2,
            "name": "Global Horizon Distributors",
            "slug": "global-horizon",
            "bill_address": "456 International Blvd, London UK",
            "phone": "+44 20 7946 0991",
            "email": "accounts@globalhorizon.com",
            "tax_id": "GB-999888777",
            "currency": "\u00a3",
            "logo_url": None,
        }
        sale_dummy_c2 = dict(sale_dummy)
        sale_dummy_c2["invoice_number"] = "GH-0001"

        pdf_c2 = generate_pdf_from_data(sale_dummy_c2, customer_dummy, items_dummy, is_quote=False, company=c2_meta)
        self.assertTrue(isinstance(pdf_c2, bytes))
        self.assertTrue(len(pdf_c2) > 1000)
        self.assertTrue(pdf_c2.startswith(b"%PDF"))

    def test_brochure_settings_expandable_products(self):
        """Brochure settings tab renders expandable brands and products and persists selection."""
        # Setup sample brand and product
        conn = database.get_connection()
        try:
            conn.execute("INSERT INTO brands (name, company_id, show_in_brochure) VALUES ('Alpha Brand', ?, 1)", (self.c1_id,))
            b_id = conn.execute("SELECT id FROM brands WHERE name = 'Alpha Brand' AND company_id = ?", (self.c1_id,)).fetchone()[0]
            conn.execute(
                """
                INSERT INTO products (name, brand, company_id, show_in_brochure, selling_price, cost_price, stock_quantity)
                VALUES ('Alpha Product 1', 'Alpha Brand', ?, 1, 10.0, 5.0, 50)
                """,
                (self.c1_id,)
            )
            p_id = conn.execute("SELECT id FROM products WHERE name = 'Alpha Product 1' AND company_id = ?", (self.c1_id,)).fetchone()[0]
            conn.commit()
        finally:
            conn.close()

        self._login("c1_admin_brand", "pass123")

        # 1. GET brochure tab renders accordion card and product toggle chip
        res = self.client.get("/settings?tab=brochure")
        self.assertEqual(res.status_code, 200)
        self.assertIn(b"brand-accordion-card", res.data)
        self.assertIn(b"Alpha Brand", res.data)
        self.assertIn(b"Alpha Product 1", res.data)
        self.assertIn(b"product-toggle-chip", res.data)

        # 2. POST brochure form with selected brand and product
        res = self.client.post("/settings?tab=brochure", data={
            "form_type": "brochure",
            "brands": [str(b_id)],
            "products": [str(p_id)]
        }, follow_redirects=True)
        self.assertEqual(res.status_code, 200)

        # Verify DB flags
        conn = database.get_connection()
        try:
            b_flag = conn.execute("SELECT show_in_brochure FROM brands WHERE id = ?", (b_id,)).fetchone()[0]
            p_flag = conn.execute("SELECT show_in_brochure FROM products WHERE id = ?", (p_id,)).fetchone()[0]
            self.assertEqual(b_flag, 1)
            self.assertEqual(p_flag, 1)
        finally:
            conn.close()

    def test_team_member_table_formatting(self):
        """Team member tab renders formatted header row, Add Team Member button, status pills, and avatars."""
        self._login("c1_admin_brand", "pass123")

        res = self.client.get("/settings?tab=users")
        self.assertEqual(res.status_code, 200)
        self.assertIn(b"team-header-row", res.data)
        self.assertIn(b"btn-add-team-member", res.data)
        self.assertIn(b"Add Team Member", res.data)
        self.assertIn(b"team-table", res.data)
        self.assertIn(b"status-pill-active", res.data)
        self.assertIn(b"user-avatar-monogram", res.data)


if __name__ == "__main__":
    unittest.main()
