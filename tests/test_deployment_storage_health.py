import json
import os
import unittest
from pathlib import Path
from unittest.mock import patch

import app as flask_app
import storage
from invoice_generator import generate_pdf_from_data


class TestDeploymentStorageAndHealth(unittest.TestCase):
    def setUp(self):
        flask_app.app.config["TESTING"] = True
        self.client = flask_app.app.test_client()

    def test_healthz_endpoint(self):
        """Verify /healthz returns 200 with healthy status and Neon services."""
        response = self.client.get("/healthz")
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.data)
        self.assertEqual(data.get("status"), "healthy")
        self.assertEqual(data.get("app"), "Pallo Multi-Tenant SaaS")
        self.assertIn(data.get("database"), ["sqlite", "postgresql"])
        self.assertIn(data.get("storage"), ["neon-object-storage", "cloudflare-r2", "local-filesystem"])
        self.assertIn("version", data)

    def test_neon_storage_live_roundtrip(self):
        """Verify storage adapter uploads to Neon Object Storage and deletes cleanly."""
        if not storage.is_neon_storage_configured():
            self.skipTest("Neon Object Storage is not configured.")

        test_content = b"fake-png-content-neon-test"
        filename = "test_neon_company_logo.png"

        saved_url = storage.save_company_logo(test_content, filename, "image/png")
        self.assertTrue(saved_url.startswith("https://"))
        self.assertIn("storage.", saved_url)
        self.assertIn("assets/logos/companies/test_neon_company_logo.png", saved_url)

        # Verify deletion from Neon
        deleted = storage.delete_company_logo(saved_url)
        self.assertTrue(deleted)

    def test_storage_fallback_to_local(self):
        """Verify storage adapter saves locally when cloud storage is unconfigured."""
        with patch.object(storage, "is_neon_storage_configured", return_value=False), \
             patch.object(storage, "is_r2_configured", return_value=False):
            test_content = b"fake-png-content-local-fallback"
            filename = "test_company_fallback_9999.png"
            
            saved_url = storage.save_company_logo(test_content, filename, "image/png")
            self.assertEqual(saved_url, f"/static/logos/companies/{filename}")
            
            local_path = storage.LOCAL_LOGOS_DIR / filename
            self.assertTrue(local_path.exists())
            self.assertEqual(local_path.read_bytes(), test_content)
            
            # Test delete
            deleted = storage.delete_company_logo(saved_url)
            self.assertTrue(deleted)
            self.assertFalse(local_path.exists())

    def test_invoice_generator_with_remote_or_local_logos(self):
        """Verify invoice generation succeeds with both local and remote/mock logo URLs."""
        sale_dummy = {
            "id": 1,
            "invoice_number": "INV-1001",
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
        company_remote_logo = {
            "id": 2,
            "name": "Beta Wholesale LLC",
            "slug": "beta-wholesale",
            "logo_url": "https://pub-sample.r2.dev/logos/companies/company_2.png",
            "currency": "$",
            "tax_id": "US-9999",
            "bill_address": "100 Industrial Parkway",
            "ship_address": "100 Industrial Parkway",
            "phone": "555-0199",
            "email": "info@betawholesale.com",
        }
        
        # Should gracefully handle the remote URL without crashing
        pdf_bytes = generate_pdf_from_data(sale_dummy, customer_dummy, items_dummy, is_quote=False, company=company_remote_logo)
        self.assertIsInstance(pdf_bytes, bytes)
        self.assertTrue(pdf_bytes.startswith(b"%PDF"))


if __name__ == "__main__":
    unittest.main()
