import os
import unittest
from unittest.mock import MagicMock, patch

import database


class TestPostgresMultiTenantSchema(unittest.TestCase):
    def setUp(self):
        self.schema_sql = database.get_postgres_schema_sql()

    def test_schema_sql_loads_successfully(self):
        self.assertIsNotNone(self.schema_sql)
        self.assertGreater(len(self.schema_sql), 500)

    def test_all_19_tables_defined(self):
        expected_tables = [
            "companies",
            "users",
            "categories",
            "brands",
            "warehouses",
            "suppliers",
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
        for tbl in expected_tables:
            self.assertIn(
                f"CREATE TABLE IF NOT EXISTS {tbl}",
                self.schema_sql,
                f"Missing CREATE TABLE for {tbl}",
            )

    def test_all_entity_tables_have_company_id_reference(self):
        entity_tables = [
            "users",
            "categories",
            "brands",
            "warehouses",
            "suppliers",
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
        for tbl in entity_tables:
            # Check that table section contains company_id referencing companies(id)
            tbl_start = self.schema_sql.find(f"CREATE TABLE IF NOT EXISTS {tbl}")
            self.assertNotEqual(tbl_start, -1, f"Table {tbl} not found")
            tbl_end = self.schema_sql.find(");", tbl_start)
            tbl_def = self.schema_sql[tbl_start:tbl_end]
            self.assertIn("company_id", tbl_def, f"Table {tbl} missing company_id")
            self.assertIn("REFERENCES companies(id)", tbl_def, f"Table {tbl} company_id does not reference companies(id)")

    def test_exact_numeric_types_for_financial_columns(self):
        # Key financial columns should be NUMERIC rather than REAL/FLOAT
        self.assertIn("cost_price NUMERIC(14, 4)", self.schema_sql)
        self.assertIn("selling_price NUMERIC(14, 4)", self.schema_sql)
        self.assertIn("grand_total NUMERIC(14, 4)", self.schema_sql)
        self.assertIn("subtotal NUMERIC(14, 4)", self.schema_sql)
        self.assertIn("amount_paid NUMERIC(14, 4)", self.schema_sql)
        self.assertIn("remaining_amount NUMERIC(14, 4)", self.schema_sql)
        self.assertIn("commission_rate NUMERIC(6, 4)", self.schema_sql)

    def test_composite_unique_constraints(self):
        # Multi-tenant scoped uniqueness checks
        self.assertIn("CONSTRAINT uq_categories_company_name UNIQUE(company_id, name)", self.schema_sql)
        self.assertIn("CONSTRAINT uq_brands_company_name UNIQUE(company_id, name)", self.schema_sql)
        self.assertIn("CONSTRAINT uq_warehouses_company_name UNIQUE(company_id, name)", self.schema_sql)
        self.assertIn("CONSTRAINT uq_sales_company_invoice UNIQUE(company_id, invoice_number)", self.schema_sql)

    def test_composite_indices_defined(self):
        expected_indices = [
            "idx_users_company_id",
            "idx_categories_company_id",
            "idx_brands_company_id",
            "idx_customers_company_id",
            "idx_warehouses_company_id",
            "idx_suppliers_company_id",
            "idx_products_company_id",
            "idx_products_company_cat",
            "idx_products_company_pub",
            "idx_sales_company_inv",
            "idx_sales_company_date",
            "idx_sales_company_status",
            "idx_sales_company_cust",
            "idx_sale_items_comp_sale",
            "idx_expenses_comp_date",
            "idx_inv_hist_comp_prod",
            "idx_inv_hist_comp_date",
        ]
        for idx in expected_indices:
            self.assertIn(f"CREATE INDEX IF NOT EXISTS {idx}", self.schema_sql, f"Missing index {idx}")

    def test_init_postgres_db_execution(self):
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_conn.cursor.return_value.__enter__.return_value = mock_cursor

        database.init_postgres_db(conn=mock_conn)

        mock_cursor.execute.assert_called_once_with(self.schema_sql)
        mock_conn.commit.assert_called_once()

    def test_init_db_dual_mode_dispatch(self):
        with patch.object(database, "is_postgres_configured", return_value=True), \
             patch.object(database, "init_postgres_db") as mock_pg:
            database.init_db()
            mock_pg.assert_called_once()

        with patch.object(database, "is_postgres_configured", return_value=False), \
             patch.object(database, "init_sqlite_db") as mock_sqlite:
            database.init_db()
            mock_sqlite.assert_called_once()


if __name__ == "__main__":
    unittest.main()
