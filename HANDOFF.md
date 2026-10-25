# Handoff: Pallo SaaS Conversion (PostgreSQL Multi-Tenant Architecture)

## Executive Summary
This project converts an existing single-business wholesale ERP ("AK Distributors LLC") into **Pallo**, a multi-tenant SaaS application running on a single shared **PostgreSQL** database.

All planning, architectural decisions, and requirement stress-testing were completed and approved via `/grill-with-docs`. The execution route is charted as a shared map of 11 decision/task tickets under `.scratch/pallo-saas/` via `/wayfinder`.

**Current Status**: Tickets 01 through 06 are completely resolved, unit-tested (44 passing tests), committed, and pushed to GitHub `main` (`277695f`). The next session can immediately claim and execute **Ticket 07** on the active frontier.

---

## Destination
A production-ready **Pallo** multi-tenant SaaS running on PostgreSQL, where multiple independent businesses can self-register, manage multi-warehouse inventory, execute sales/POS, and generate custom-branded PDF invoices, with AK Distributors preserved as Company 1 with 100% data fidelity and zero cross-tenant leakage.

---

## Progress So Far (Resolved & Pushed)

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

---

## Standing Context & Established Rules
1. **Database Engine**: Centralized PostgreSQL with `ThreadedConnectionPool` using `DATABASE_URL` (supports local Postgres and free serverless cloud Postgres like Neon/Supabase) with seamless fallback to SQLite.
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
- **Implementation Plan**: [pallo_saas_single_db_plan.md](file:///Users/hassaanjazz/.gemini/antigravity-ide/brain/07de88ae-4a5a-42ca-abf8-a089338194b7/pallo_saas_single_db_plan.md)
- **ADRs**:
  - [ADR 0001: Shared Database Multi-Tenancy Architecture](file:///docs/adr/0001-shared-db-multi-tenancy-and-flask-evolution.md)
  - [ADR 0002: Global User Identity & Unified Authentication](file:///docs/adr/0002-global-user-identity-and-unified-auth.md)
  - [ADR 0003: Role-Based Financial & Cost Protection](file:///docs/adr/0003-role-based-financial-and-cost-protection.md)
  - [ADR 0004: Tenant Lifecycle & Soft-Deactivation Policy](file:///docs/adr/0004-tenant-lifecycle-and-soft-deactivation.md)
  - [ADR 0005: Database Engine Transition to PostgreSQL](file:///docs/adr/0005-database-engine-transition-to-postgresql.md)
- **Domain Glossary**: [GLOSSARY.md](file:///GLOSSARY.md)
- **Milestone Tracker**: [docs/agents/issue-tracker.md](file:///docs/agents/issue-tracker.md)

---

## Wayfinder Issue Map & Next Immediate Task

### Active Frontier Ticket (Take this first)
- 🟢 **[07-scope-customers-and-sales-pos.md](file:///.scratch/pallo-saas/issues/07-scope-customers-and-sales-pos.md)**
  - *Status*: Open, Unblocked (06 resolved).
  - *Goal*: Scope customer records, customer ledgers/payments, POS checkout (`/pos`), and sales history (`/sales`, `/sale/<id>`) by `company_id`. Route sequential invoice number generation to tenant-specific prefix and sequence counter via `get_next_invoice_number(company_id)`.

### Remaining Downstream Tickets
- **08-scope-warehouses-transfers-purchases-expenses.md** (Blocked by 07)
- **09-dynamic-pdf-invoicing-and-company-branding.md** (Blocked by 07)
- **10-superadmin-platform-governance.md** (Blocked by 04 - Ready to run after 07-09)
- **11-tenant-isolation-automated-test-suite.md** (Blocked by 08, 09, 10)

---

## Suggested Skills for the Next Agent
- `wayfinder`: To claim, execute, and resolve tickets one by one per `.scratch/pallo-saas/map.md`.
- `security-and-hardening`: For parameterized SQL queries and cross-tenant data protection.
- `test-driven-development`: For expanding unit tests for customer ledgers and sales isolation.

---

## Prompt to Start Next Session
Copy and paste this into the new window:
```text
/wayfinder We are converting the ERP to Pallo Multi-Tenant SaaS on PostgreSQL. Review the handoff document at HANDOFF.md and .scratch/pallo-saas/map.md. Claim and start working on Ticket 07 (.scratch/pallo-saas/issues/07-scope-customers-and-sales-pos.md).
```
