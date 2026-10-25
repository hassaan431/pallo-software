# Scope Customers, Point of Sale and Invoicing

Type: task
Status: closed
Assignee: Antigravity
Blocked by: none (06 resolved)

## Question

How do we scope all customer ledgers, POS checkout routes, and sales history in [app.py](file:///Users/hassaanjazz/Desktop/Projects/SaaS/Pallo/app.py) to `company_id = current_user.company_id`, while routing sequential invoice generation to the company's specific prefix (`INV-`, `AK-`) and sequence counter via `get_next_invoice_number(company_id)`?

## Resolution & Implementation

1. **Database & Sequential Invoice Number Generation**:
   - Updated `get_next_invoice_number(company_id: int = 1)` in [database.py](file:///Users/hassaanjazz/Desktop/Projects/SaaS/Pallo/database.py) to accept `company_id`.
   - Queries tenant-specific `sales.invoice_number` for invoices starting with the company's `invoice_prefix` (e.g., `AK-` for Company 1, `INV-` by default or custom prefixes like `TC1-`, `S2-`).
   - Defaults Company 1 (`AK Distributors LLC`) invoice prefix to `'AK-'` in `_ensure_sqlite_companies_support(conn)` to preserve continuous sequence (`AK-001012`), while newly registered tenants start at their configured starting number with their company prefix.

2. **Customer Routes Scoped**:
   - `/customers`, `/customers/add`, `/customers/edit/<customer_id>`, `/customers/delete/<customer_id>`, `/customers/list`, and `/customers/<customer_id>/history` scoped with `company_id = current_user.company_id`.
   - Returns 404 if editing or deleting a customer belonging to another company.

3. **Sales & POS Routes Scoped**:
   - `/sales` and `/sales/next-invoice`: fetch tenant-specific next invoice number via `get_next_invoice_number(cid)`.
   - `/sales/new`: validates tenant customer, products, warehouse; generates tenant invoice number (`Q-<num>` for quotes, `<prefix>-<num>` for sales); inserts `sales`, `sale_items`, and `inventory_history` with `company_id`.
   - `/sales/data`: queries tenant sales and masks cost/profit margins for non-admin users (`salesman`, `warehouse_manager`) per ADR 0003.
   - `/sales/<sale_id>/details`: scoped to `s.company_id = cid`; non-admin role receives `profit_margin = None`, `profit_amount = None`, and `total_cost = None`.
   - `/sales/by-invoice/<invoice_number>`: scoped with `s.invoice_number = ? AND s.company_id = ?`.
   - `/sales/<id>/invoice/pdf`: enforces tenant isolation on sale and customer, formats filename dynamically.
   - `/sales/<sale_id>/mark_sale`: converts quote to sale using company's `invoice_prefix`, updates `sales`, verifies tenant stock, and inserts `inventory_history` with `company_id`.
   - `/sales/update/<sale_id>`: scopes sale lookup, uniqueness check, customer check, stock check, sales update, `sale_items` insert, and `inventory_history` insert with `company_id`.
   - `/sales/delete/<id>`: verifies tenant sale, restores warehouse inventory, and inserts `inventory_history` with `company_id`.
   - `/sales/<sale_id>/record_payment`: verifies tenant ownership before applying payment.
   - `/sales/export` & `/sales/import-csv`: multi-tenant scoped import validation and CSV export.
   - `/pos` & `/pos/submit_order`: scoped warehouse query, tenant customer creation/verification, tenant invoice generation, sales/sale_items insertion with `company_id`, and stock deduction.

4. **Dashboard & Reporting Scoped**:
   - `/dashboard`: scoped all daily/monthly revenue, costs, expenses, recent sales, upcoming payments, and chart data with `company_id = current_user.company_id`.
   - `parse_date_filters`: appends `s.company_id = ?` to all date-filtered reports.
   - `/reports/stock-distribution/data`, `/reports`, `/reports/inventory-additions`, `/reports/supplier-purchases/<id>`, and `/reports/profit`: fully isolated by `company_id`.

5. **Invoice Generator & Templates**:
   - [invoice_generator.py](file:///Users/hassaanjazz/Desktop/Projects/SaaS/Pallo/invoice_generator.py): dynamic company header based on tenant company record (name, address, phone, email) while preserving AK Distributors styling for Company 1.
   - [templates/sales.html](file:///Users/hassaanjazz/Desktop/Projects/SaaS/Pallo/templates/sales.html): quote conversion note displays dynamic `{{ current_company.invoice_prefix or "INV-" }}`.

6. **Unit Tests**:
   - Created [tests/test_customer_sales_scoping.py](file:///Users/hassaanjazz/Desktop/Projects/SaaS/Pallo/tests/test_customer_sales_scoping.py) with 6 comprehensive unit tests.
   - All 50 tests in project test suite pass.
