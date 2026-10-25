# Build and Run SQLite to PostgreSQL Migration Script

Type: task
Status: closed
Assignee: Antigravity
Blocked by: none (02 resolved)

## Question

How do we build and execute a robust, zero-loss extraction and verification script (`migrate_sqlite_to_postgres.py`) that reads all rows from `database.db`, writes them into PostgreSQL under `company_id = 1` ("AK Distributors LLC"), resets PostgreSQL sequence counters (`setval`), and verifies 100% row-count parity across every table?

## Resolution

1. **Migration Script Architecture ([migrate_sqlite_to_postgres.py](file:///Users/hassaanjazz/Desktop/Projects/SaaS/Pallo/migrate_sqlite_to_postgres.py))**:
   - Built a standalone, zero-loss migration tool that connects to [database.db](file:///Users/hassaanjazz/Desktop/Projects/SaaS/Pallo/database.db) in read-only mode and PostgreSQL via `DATABASE_URL` (or `--url`).
   - Ensures PostgreSQL multi-tenant schema is initialized before loading.
   - Upserts Company 1 ("AK Distributors LLC", `slug = 'ak-distributors'`, `invoice_prefix = 'AK-'`, `currency = '$'`) with exact legal business details.

2. **Topological Order & Foreign Key Integrity**:
   - Migrates tables in strict dependency order:
     `companies` -> `warehouses` -> `categories` -> `brands` -> `suppliers` -> `users` -> `customers` -> `products` -> `product_variants` -> `warehouse_inventory` -> `sales` -> `sale_items` -> `purchases` -> `purchase_items` -> `supplier_payments` -> `expenses` -> `inventory_transfers` -> `inventory_transfer_items` -> `inventory_history`.
   - Maps each record with `company_id = 1` while preserving existing primary keys (`id`).
   - Handles nullable foreign-key orphan sanitation (e.g. sales referencing historical deleted customer IDs, or payments referencing deleted purchase IDs sanitized to `NULL` to avoid foreign key violations while preserving financial ledger entries).
   - Automatically injects parent stubs for missing parents in hard foreign keys (e.g. historical archived transfer records) ensuring 100% of rows are loaded.

3. **Sequence Counter Synchronization**:
   - Automatically resets PostgreSQL sequences for all tables using:
     `SELECT setval(pg_get_serial_sequence('<table>', 'id'), COALESCE(MAX(id), 1), true)`
     ensuring that future tenant inserts auto-increment cleanly above existing historical IDs.

4. **Parity Audit & Transaction Safety**:
   - Compares row counts between SQLite and PostgreSQL `WHERE company_id = 1`.
   - Formats a clear ASCII verification audit table.
   - Requires 100% data parity before committing the transaction; rolls back automatically on error or when `--dry-run` is requested.
   - Leaves original SQLite `database.db` completely untouched as a backup.

5. **Automated Verification**:
   - Authored unit test suite [tests/test_migration.py](file:///Users/hassaanjazz/Desktop/Projects/SaaS/Pallo/tests/test_migration.py) testing topological ordering, metadata completeness, row sanitization, orphan handling, and audit reporting. All 21 tests in the project test suite pass cleanly.
