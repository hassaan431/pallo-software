# Define PostgreSQL Multi-Tenant Schema and DDL

Type: task
Status: closed
Assignee: Antigravity
Blocked by: none (01 resolved)

## Question

How do we define the PostgreSQL multi-tenant schema in [database.py](file:///Users/hassaanjazz/Desktop/Projects/SaaS/Pallo/database.py) including the `companies` table, `company_id` foreign keys across all 18 entity tables, exact `NUMERIC(14, 4)` columns for financial accuracy, and composite indices on `(company_id, ...)` for sub-millisecond query filtering?

## Resolution

1. **Schema DDL Definition ([schema_postgres.sql](file:///Users/hassaanjazz/Desktop/Projects/SaaS/Pallo/schema_postgres.sql))**:
   - Defined master tenant table `companies` storing tenant metadata (`name`, `slug` UNIQUE, `currency`, `invoice_prefix`, `starting_invoice_number`, `bill_address`, `ship_address`, `phone`, `email`, `tax_id`, `logo_url`, `max_warehouses`, `is_active` for soft-deactivation).
   - Created all 18 multi-tenant entity tables with explicit `company_id INTEGER REFERENCES companies(id) ON DELETE CASCADE`:
     `users`, `categories`, `brands`, `warehouses`, `suppliers`, `customers`, `products`, `product_variants`, `warehouse_inventory`, `sales`, `sale_items`, `purchases`, `purchase_items`, `supplier_payments`, `expenses`, `inventory_transfers`, `inventory_transfer_items`, and `inventory_history`.

2. **Tenant-Scoped Uniqueness Constraints**:
   - Replaced single-tenant global unique constraints with composite multi-tenant constraints so independent companies can have identical entity names without collisions:
     - `uq_categories_company_name UNIQUE(company_id, name)`
     - `uq_brands_company_name UNIQUE(company_id, name)`
     - `uq_warehouses_company_name UNIQUE(company_id, name)`
     - `uq_sales_company_invoice UNIQUE(company_id, invoice_number)`
     - `uq_warehouse_inventory UNIQUE(warehouse_id, product_id)`
   - Retained global uniqueness on `users.username` for zero-friction unified authentication (`/login`) per ADR 0002.

3. **Exact Financial Precision**:
   - Specified `NUMERIC(14, 4)` across all monetary and inventory quantity fields (`cost_price`, `selling_price`, `stock_quantity`, `grand_total`, `subtotal`, `amount_paid`, `remaining_amount`, `discount_amount`, `amount`, `quantity`, `quantity_change`, `packing_multiplier`) to eliminate floating-point penny rounding issues.
   - Specified `NUMERIC(6, 4)` for commission rates.

4. **Multi-Tenant Composite & High-Performance Indices**:
   - Built indices on `company_id` across all entity tables.
   - Built composite indices on frequently queried tenant filters:
     - `idx_sales_company_inv ON sales(company_id, invoice_number)`
     - `idx_sales_company_date ON sales(company_id, invoice_date)`
     - `idx_sales_company_status ON sales(company_id, status)`
     - `idx_sales_company_cust ON sales(company_id, customer_id)`
     - `idx_products_company_cat ON products(company_id, category_id)`
     - `idx_products_company_pub ON products(company_id, is_public)`
     - `idx_sale_items_comp_sale ON sale_items(company_id, sale_id)`
     - `idx_inv_hist_comp_date ON inventory_history(company_id, created_at)`
     - `idx_inv_hist_comp_prod ON inventory_history(company_id, product_id)`

5. **Application DDL Integration & Automated Verification**:
   - Integrated `get_postgres_schema_sql()` and `init_postgres_db(conn=None)` into [database.py](file:///Users/hassaanjazz/Desktop/Projects/SaaS/Pallo/database.py).
   - Refactored `init_db()` to automatically dispatch to `init_postgres_db()` when `DATABASE_URL` is configured, while falling back to `init_sqlite_db()` when empty.
   - Authored [tests/test_postgres_schema.py](file:///Users/hassaanjazz/Desktop/Projects/SaaS/Pallo/tests/test_postgres_schema.py) verifying all 19 tables, `company_id` foreign keys, `NUMERIC` types, composite unique constraints, indices, and dual-mode dispatch. All 16 tests in the test suite pass.
