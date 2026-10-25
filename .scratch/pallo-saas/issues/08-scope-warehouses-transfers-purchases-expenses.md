# Scope Warehouses, Stock Transfers, Purchases and Expenses

Type: task
Status: closed
Assignee: Antigravity
Blocked by: none (07 resolved)

## Question

How do we scope warehouse facilities, inter-warehouse transfers, supplier purchases, and operational expenses in [app.py](file:///Users/hassaanjazz/Desktop/Projects/SaaS/Pallo/app.py) to `company_id`, enforcing strict validation that source and destination warehouses belong to the same company, and restricting expense management strictly to the `admin` role?

## Resolution

All warehouse facilities, stock transfers, supplier ledgers, purchase orders, operational expenses, and staff management have been fully scoped to `company_id` with comprehensive validation:

1. **Warehouse Facilities & Plan Limits**:
   - `/warehouses`, `/api/warehouse/recent_sales`, `/api/warehouse/inventory`, `/warehouses/add`, and `/warehouses/edit/<id>` scoped by `company_id = cid`.
   - Plan limit enforced: checks `companies.max_warehouses` before permitting creation of additional facilities.
   - Cross-tenant editing blocked with 404.

2. **Inter-Warehouse Stock Transfers**:
   - `/inventory/transfer/new`, `/inventory/transfer`, `/inventory/transfer/edit/<id>`, `/inventory/transfers`, and `/inventory/transfers/<id>/delete` scoped by `company_id = cid`.
   - Validates that source and destination warehouses are distinct and belong to the authenticated user's company; rejects cross-tenant transfers with 400.
   - Validates all transferred products belong to the tenant company.
   - Stored `company_id` on `inventory_transfers`, `inventory_transfer_items`, `warehouse_inventory`, and `inventory_history`.
   - Cross-tenant edit/delete blocked with 404.

3. **Suppliers & Ledger History**:
   - `/suppliers`, `/suppliers/add`, `/suppliers/edit/<id>`, `/suppliers/delete/<id>`, and `/suppliers/<id>/history` scoped by `company_id = cid`.
   - Supplier total balance and paid metrics filtered by `company_id = cid`.
   - Cross-tenant supplier modification or history inspection blocked with 404.

4. **Purchase Orders & Supplier Payments**:
   - `/purchases`, `/purchases/new`, `/purchases/edit/<id>`, `/api/purchases/<id>`, `/api/purchases/<id>/delete`, `/purchases/<id>`, and `/api/supplier_payments` scoped by `company_id = cid`.
   - Validates supplier, warehouse, and products belong to tenant company before creation/update.
   - Associated `company_id` on `purchases`, `purchase_items`, `supplier_payments`, `warehouse_inventory`, and `inventory_history`.
   - Cross-tenant detail view, update, delete, or payment blocked with 404/400.

5. **Operational Expenses & Admin Protection**:
   - `/expenses`, `/expenses/add`, `/expenses/edit/<id>`, `/expenses/delete/<id>` protected by `@admin_required` (ADR 0003). Non-admin roles rejected.
   - Partitioned strictly by `company_id = cid` for listing, metrics, and distinct category suggestions.
   - Cross-tenant edit or delete returns 404.

6. **Staff / User Management**:
   - `/users`, `/users/add`, `/users/toggle_active/<id>`, `/users/edit/<id>`, `/users/reset_password` scoped by `company_id = cid`.
   - Cannot deactivate own user; cross-tenant edits or password resets return 404.

7. **Automated Verification**:
   - Created test suite [tests/test_warehouse_purchases_scoping.py](file:///Users/hassaanjazz/Desktop/Projects/SaaS/Pallo/tests/test_warehouse_purchases_scoping.py) with 6 comprehensive unit tests passing. Total passing project tests: 56.
