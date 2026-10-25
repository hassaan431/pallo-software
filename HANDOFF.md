# Handoff: Pallo SaaS Conversion (PostgreSQL Multi-Tenant Architecture)

## Executive Summary
This project converts an existing single-business wholesale ERP ("AK Distributors LLC") into **Pallo**, a multi-tenant SaaS application running on a single shared **PostgreSQL** database.

All planning, architectural decisions, and requirement stress-testing were completed and approved via `/grill-with-docs`. The execution route is charted as a shared map of 11 decision/task tickets under `.scratch/pallo-saas/` via `/wayfinder`.

**Current Status**: All 11 tickets (Tickets 01 through 11) and all 7 project milestones (M1 through M7) are completely resolved, unit-tested (74 passing tests across the entire repository), verified locally, and documented.

---

## Destination
A production-ready **Pallo** multi-tenant SaaS running on PostgreSQL, where multiple independent businesses can self-register, manage multi-warehouse inventory, execute sales/POS, and generate custom-branded PDF invoices, with AK Distributors preserved as Company 1 with 100% data fidelity and zero cross-tenant leakage.

---

## Progress So Far (Resolved)

- ✅ **Ticket 01** ([01-provision-postgres-connection-and-pooling.md](file:///.scratch/pallo-saas/issues/01-provision-postgres-connection-and-pooling.md)):
  - Added `psycopg2-binary`, `python-dotenv`.
  - Built `ThreadedConnectionPool` with `PooledConnectionWrapper` and fallback to SQLite.
- ✅ **Ticket 02** ([02-define-postgres-multi-tenant-schema.md](file:///.scratch/pallo-saas/issues/02-define-postgres-multi-tenant-schema.md)):
  - Created full PostgreSQL multi-tenant schema with `company_id`, exact `NUMERIC(14, 4)`, and composite indexes.
- ✅ **Ticket 03** ([03-build-sqlite-to-postgres-migration-script.md](file:///.scratch/pallo-saas/issues/03-build-sqlite-to-postgres-migration-script.md)):
  - Automated migration tool (`migrate_sqlite_to_postgres.py`) with FK sanitization, sequence sync, and 100% parity verification.
- ✅ **Ticket 04** ([04-unified-auth-session-scoping-and-context.md](file:///.scratch/pallo-saas/issues/04-unified-auth-session-scoping-and-context.md)):
  - User model scoped by `company_id`, active company checks on login, soft-deactivation session termination, and global template context injection (`current_company`, `app_name = 'Pallo'`).
- ✅ **Ticket 05** ([05-self-serve-company-registration.md](file:///.scratch/pallo-saas/issues/05-self-serve-company-registration.md)):
  - Self-serve `/register` page with collision-proof slug generation, atomic provisioning of default warehouse, starter categories, and tenant admin account.
- ✅ **Ticket 06** ([06-scope-products-inventory-and-cost-masking.md](file:///.scratch/pallo-saas/issues/06-scope-products-inventory-and-cost-masking.md)):
  - Scoped `/inventory`, categories, brands, product APIs, and public catalogue/brochure helpers by `company_id`.
  - Added `PooledCursorWrapper` to transparently translate `?` to `%s` for PostgreSQL cursor queries.
  - Implemented ADR 0003 commercial privacy: strictly masked `cost_price`, `stock_value`, and profit margin data for non-admin roles (`salesman`, `warehouse_manager`) across JSON APIs, HTML templates, and CSV downloads.
- ✅ **Ticket 07** ([07-scope-customers-and-sales-pos.md](file:///.scratch/pallo-saas/issues/07-scope-customers-and-sales-pos.md)):
  - Scoped customer ledgers, sales CRUD, POS checkout, reports, and dashboard by `company_id`.
  - Tenant-specific sequential invoice numbering (`AK-`, `INV-`, etc.) via `get_next_invoice_number(company_id)`.
  - Dynamic invoice PDF branding in `invoice_generator.py` preserving Company 1 dual logos/formatting.
  - Quotation conversion to tenant prefix and ADR 0003 sales profit margin masking for non-admins.
- ✅ **Ticket 08** ([08-scope-warehouses-transfers-purchases-expenses.md](file:///.scratch/pallo-saas/issues/08-scope-warehouses-transfers-purchases-expenses.md)):
  - Scoped warehouse facilities with `max_warehouses` plan limit enforcement.
  - Scoped inter-warehouse transfers with strict validation that source and destination facilities belong to the same tenant company, preventing cross-tenant stock movement.
  - Scoped suppliers and ledger history; scoped purchase orders and supplier payments.
  - Scoped operational expenses strictly restricted to `admin` role per ADR 0003.
  - Scoped staff/user management with self-deactivation protection and cross-tenant mutation blocks.
  - Created test suite [tests/test_warehouse_purchases_scoping.py](file:///tests/test_warehouse_purchases_scoping.py) with 6 passing unit tests.
- ✅ **Ticket 09** ([09-dynamic-pdf-invoicing-and-company-branding.md](file:///.scratch/pallo-saas/issues/09-dynamic-pdf-invoicing-and-company-branding.md)):
  - Built Company Profile & White-Label Settings portal (`/settings/company`) for tenant admins to view and manage company details.
  - Implemented secure logo upload with safety guardrails: max 2MB file size cap, allowed image extensions (`.png`, `.jpg`, `.jpeg`, `.webp`, `.svg`).
  - Updated sidebar brand header and document title in [templates/base.html](file:///templates/base.html) to dynamically render current tenant's logo and company name.
  - Updated invoice PDF generator [invoice_generator.py](file:///invoice_generator.py) to dynamically format rates, amounts, totals, and balances with the tenant's currency symbol.
  - Added unit test suite [tests/test_company_branding_settings.py](file:///tests/test_company_branding_settings.py) with 7 passing unit tests.
- ✅ **Ticket 10** ([10-superadmin-platform-governance.md](file:///.scratch/pallo-saas/issues/10-superadmin-platform-governance.md)):
  - Enforced SuperAdmin security gate (`@superadmin_required`) restricting platform management to `role == 'superadmin'`.
  - Built Platform Governance Dashboard (`/superadmin` and [templates/superadmin.html](file:///templates/superadmin.html)) aggregating registered tenants, active/paused status, platform sales GMV, orders count, total catalog products, and total platform accounts.
  - Implemented 1-click tenant soft-deactivation toggle (`/superadmin/company/<id>/toggle_status`) per ADR 0004 with immediate session interception while preserving transactional records.
  - Protected Master Company 1 ("AK Distributors LLC") from deactivation.
  - Added tenant warehouse plan capacity manager (`/superadmin/company/<id>/update_plan`).
  - Added unit test suite [tests/test_superadmin_governance.py](file:///tests/test_superadmin_governance.py) with 4 passing unit tests.
- ✅ **Ticket 11** ([11-tenant-isolation-automated-test-suite.md](file:///.scratch/pallo-saas/issues/11-tenant-isolation-automated-test-suite.md)):
  - Built comprehensive automated tenant isolation test suite [tests/test_saas_isolation.py](file:///tests/test_saas_isolation.py) with 7 test cases covering product cross-tenant isolation, cross-tenant inter-warehouse stock transfer rejection, customer & accounts receivable isolation, independent sequential invoice numbering, salesman commercial privacy cost masking (ADR 0003), public tenant catalogue & brochure routing (`/c/<company_slug>/catalogue`, `/c/<company_slug>/brochure`) with 250-item safety cap (Milestone 5), and soft-deactivation session termination with SuperAdmin oversight (ADR 0004).
  - All 74 tests across the entire test suite pass with 100% green status.

---

## Standing Context & Established Rules
1. **Database Engine**: Centralized PostgreSQL with `ThreadedConnectionPool` using `DATABASE_URL` with seamless fallback to SQLite.
2. **Multi-Tenancy**: Single shared database partitioned by `company_id`. All queries strictly scoped (`WHERE company_id = ?`).
3. **Preserve AK Distributors**: Existing `database.db` SQLite data is preserved under `company_id = 1` ("AK Distributors LLC") with zero downtime/data loss.
4. **Branding & UI**: Keep the software's existing emerald (`#10b981`) and slate design system tokens. Do not alter color tokens. Global app brand is **Pallo**.
5. **Deployment & Restart Rules** (from `.agents/AGENTS.md`):
   - Test locally first: Run `python3 launch.py` in background.
   - Restart rule: Automatically restart server when making backend/template changes using:
     `lsof -t -i :5000 | xargs kill -9 && python3 launch.py`
   - Push to GitHub only after user explicitly verifies and approves.
   - Inform user to run `git pull` on PythonAnywhere console and reload web app for production deploys.

---

## Canonical Documentation & Artifacts
- **Wayfinder Map**: [.scratch/pallo-saas/map.md](file:///.scratch/pallo-saas/map.md)
- **ADRs**:
  - [ADR 0001: Shared Database Multi-Tenancy Architecture](file:///docs/adr/0001-shared-db-multi-tenancy-and-flask-evolution.md)
  - [ADR 0002: Global User Identity & Unified Authentication](file:///docs/adr/0002-global-user-identity-and-unified-auth.md)
  - [ADR 0003: Role-Based Financial & Cost Protection](file:///docs/adr/0003-role-based-financial-and-cost-protection.md)
  - [ADR 0004: Tenant Lifecycle & Soft-Deactivation Policy](file:///docs/adr/0004-tenant-lifecycle-and-soft-deactivation.md)
  - [ADR 0005: Database Engine Transition to PostgreSQL](file:///docs/adr/0005-database-engine-transition-to-postgresql.md)
- **Domain Glossary**: [GLOSSARY.md](file:///GLOSSARY.md)
- **Milestone Tracker**: [docs/agents/issue-tracker.md](file:///docs/agents/issue-tracker.md) (All M1 - M7 milestones completed)
- `security-and-hardening`: For validating tenant isolation assertions and cross-company rejection.
- `test-driven-development`: For end-to-end multi-tenant isolation testing.

---

## Prompt to Start Next Session
Copy and paste this into the new window:
```text
We have completed all 11 tickets for the Pallo Multi-Tenant SaaS conversion on PostgreSQL. Please review HANDOFF.md, .scratch/pallo-saas/map.md, and docs/agents/issue-tracker.md for full context. Run the automated test suite (`python3 -m unittest discover tests`) to verify the 74 tests pass, ensure the local server is running on port 5000 via `python3 launch.py`, and let me know the status and next steps for production deployment and SaaS operations.
```
