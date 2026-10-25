# Tenant Isolation and Multi-Tenancy Automated Test Suite

Type: task
Status: closed
Blocked by: none (08, 09, 10 resolved)

## Question

How do we construct an end-to-end automated test suite (`test_saas_isolation.py`) to systematically assert that cross-company data leakage is impossible across inventory, customer ledgers, sales records, and invoice number sequences, and that soft-deactivated companies cannot log in?

## Resolution Summary

Implemented comprehensive end-to-end automated multi-tenant isolation test suite in `tests/test_saas_isolation.py` (7 tests, all passing):

1. **Cross-Tenant Product Isolation (`test_cross_tenant_product_isolation`)**:
   - Asserts Tenant A cannot see Tenant B's products via `/products/list`.
   - Asserts Tenant A cannot modify Tenant B's products (`/products/edit/<id>` returns 404).

2. **Inter-Warehouse Transfer Cross-Tenant Blocking (`test_inter_warehouse_transfer_cross_tenant_rejection`)**:
   - Asserts attempting to transfer stock from Tenant A warehouse to Tenant B warehouse fails with HTTP 400 (`"One or both selected warehouses are invalid or unauthorized."`).

3. **Customer & Accounts Receivable Isolation (`test_customer_and_accounts_receivable_isolation`)**:
   - Asserts Tenant A only sees their own customers in `/customers/list`.
   - Asserts recording payments on another tenant's customer returns HTTP 404.

4. **Independent Sequential Invoicing (`test_independent_tenant_sequential_invoice_numbering`)**:
   - Asserts Tenant A (`ISOA-`) and Tenant B (`ISOB-`) have independent sequential invoice number counters starting from 000001, without collisions or counter bleed.

5. **Commercial Privacy Cost Masking (`test_commercial_privacy_cost_masking_for_salesman`)**:
   - Asserts salesmen cannot see `cost_price` (`None`) in `/products/list` per ADR 0003.

6. **Public Tenant Catalogue & Brochure Routing (`test_public_tenant_catalogue_and_brochure_routing`)**:
   - Asserts `/c/<slug>/catalogue` and `/c/<slug>/brochure` load successfully for active tenants.
   - Asserts non-existent slug returns 404.
   - Asserts root `/catalogue` and `/brochure` remain backwards-compatible for Company 1.

7. **Soft-Deactivation & Session Termination (`test_soft_deactivation_session_termination_and_superadmin_oversight`)**:
   - Asserts deactivating a tenant (`is_active = 0`) blocks new logins and terminates existing active user sessions.
   - Asserts SuperAdmin maintains oversight access.

All 74 tests across the entire test suite pass with 100% green status.
