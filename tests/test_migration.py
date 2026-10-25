import unittest
from unittest.mock import MagicMock, patch

import migrate_sqlite_to_postgres as mig


class TestMigrationLogic(unittest.TestCase):
    def test_table_order_contains_all_tables(self):
        expected = [
            "companies",
            "warehouses",
            "categories",
            "brands",
            "suppliers",
            "users",
            "customers",
            "products",
            "product_variants",
            "warehouse_inventory",
            "sales",
            "sale_items",
            "purchases",
            "purchase_items",
            "supplier_payments",
            "expenses",
            "inventory_transfers",
            "inventory_transfer_items",
            "inventory_history",
        ]
        self.assertEqual(mig.TABLE_ORDER, expected)

    def test_company_1_metadata(self):
        meta = mig.COMPANY_1_METADATA
        self.assertEqual(meta["id"], 1)
        self.assertEqual(meta["name"], "AK Distributors LLC")
        self.assertEqual(meta["slug"], "ak-distributors")
        self.assertEqual(meta["currency"], "$")
        self.assertEqual(meta["invoice_prefix"], "AK-")

    def test_sanitize_row_sets_company_id(self):
        row = {"id": 10, "name": "Test Product", "cost_price": 5.0}
        valid_ids = {}
        sanitized = mig.sanitize_row_for_postgres("products", row, valid_ids)
        self.assertEqual(sanitized["company_id"], 1)
        self.assertEqual(sanitized["name"], "Test Product")

    def test_sanitize_orphan_nullable_foreign_keys(self):
        valid_ids = {
            "customers": {2, 3},
            "purchases": {10, 11},
            "suppliers": {5},
        }

        # Orphan customer on sale
        sale_orphan = {"id": 1, "customer_id": 999}
        clean_sale = mig.sanitize_row_for_postgres("sales", sale_orphan, valid_ids)
        self.assertIsNone(clean_sale["customer_id"])

        # Valid customer on sale
        sale_valid = {"id": 2, "customer_id": 3}
        clean_valid_sale = mig.sanitize_row_for_postgres("sales", sale_valid, valid_ids)
        self.assertEqual(clean_valid_sale["customer_id"], 3)

        # Orphan purchase on supplier payment
        pay_orphan = {"id": 1, "purchase_id": 1}
        clean_pay = mig.sanitize_row_for_postgres("supplier_payments", pay_orphan, valid_ids)
        self.assertIsNone(clean_pay["purchase_id"])

        # Orphan supplier on inventory history
        hist_orphan = {"id": 1, "supplier_id": 99}
        clean_hist = mig.sanitize_row_for_postgres("inventory_history", hist_orphan, valid_ids)
        self.assertIsNone(clean_hist["supplier_id"])

    def test_verify_migration_reporting(self):
        perfect_stats = {
            "products": (194, 194),
            "sales": (95, 95),
            "customers": (4, 4),
        }
        self.assertTrue(mig.verify_migration(perfect_stats))

        mismatched_stats = {
            "products": (194, 190),  # Lost records
            "sales": (95, 95),
        }
        self.assertFalse(mig.verify_migration(mismatched_stats))


if __name__ == "__main__":
    unittest.main()
