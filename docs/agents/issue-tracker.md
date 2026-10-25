# Pallo SaaS Conversion — Issue & Progress Tracker

This document tracks implementation items, technical decisions, and milestones for converting the ERP into the Pallo multi-tenant SaaS.

## Architecture Decisions (ADRs)

- [x] **[ADR 0001: Shared Database Multi-Tenancy Architecture](../adr/0001-shared-db-multi-tenancy-and-flask-evolution.md)**
- [x] **[ADR 0002: Global User Identity & Unified Authentication](../adr/0002-global-user-identity-and-unified-auth.md)**
- [x] **[ADR 0003: Role-Based Financial & Cost Protection](../adr/0003-role-based-financial-and-cost-protection.md)**
- [x] **[ADR 0004: Tenant Lifecycle & Soft-Deactivation Policy](../adr/0004-tenant-lifecycle-and-soft-deactivation.md)**
- [x] **[ADR 0005: Database Engine Transition to PostgreSQL](../adr/0005-database-engine-transition-to-postgresql.md)**
- [x] **[GLOSSARY.md](../../GLOSSARY.md)** (Canonical domain terms)

---

## Execution Milestones

- [ ] **M1: PostgreSQL Setup, Schema Creation & Data Migration**
  - [x] Add `psycopg2-binary` and `python-dotenv` to dependencies.
  - [x] Configure `DATABASE_URL` connection management with `ThreadedConnectionPool`.
  - [x] Build PostgreSQL multi-tenant schema with `company_id`, exact `NUMERIC` types, and composite indices.
  - [ ] Write and run `migrate_sqlite_to_postgres.py` to transfer 100% of AK Distributors data to `company_id = 1`.
  - [ ] Add query helpers in `database.py` with `RealDictCursor`.

- [ ] **M2: Authentication, Tenant Scoping & Self-Serve Signup**
  - [ ] Extend Flask-Login `User` with `company_id`.
  - [ ] Implement `@app.context_processor` for `current_company`.
  - [ ] Create `/register` self-serve onboarding page with auto-slug generation.
  - [ ] Seed default "Main Warehouse" and starter categories for newly registered companies.
  - [ ] Update `/login` for unified sign-in with active company validation.

- [ ] **M3: Query Scoping & Commercial Privacy (app.py)**
  - [ ] Scope Products, Categories, Brands (`company_id`). Mask `cost_price` for non-admins.
  - [ ] Scope Customers & Ledgers (`company_id`).
  - [ ] Scope Sales, POS, and Invoices (`company_id`).
  - [ ] Scope Warehouses & Inventory Transfers (`company_id`).
  - [ ] Scope Purchases & Suppliers (`company_id`).
  - [ ] Scope Expenses & Financial Reports (`company_id`, admin-only).
  - [ ] Scope User/Staff Management (`company_id`).

- [ ] **M4: Dynamic White-Labeling & Invoicing**
  - [ ] Dynamic invoice PDF generation (`invoice_generator.py`) based on company settings (preserving AK Distributors formatting for Company 1).
  - [ ] Company profile & branding settings page (`/settings/company`) with 2MB logo upload guardrails.
  - [ ] Dynamic sidebar branding and company name badge.

- [ ] **M5: Public Tenant Catalogues & Resource Guardrails**
  - [ ] Implement `/c/<company_slug>/catalogue` and `/c/<company_slug>/brochure`.
  - [ ] Keep root `/catalogue` and `/brochure` backwards compatible to Company 1.
  - [ ] Apply 250-item safety cap on brochure PDF exports.

- [ ] **M6: SuperAdmin Platform Management**
  - [ ] Build `/superadmin` dashboard for platform metrics and soft-deactivation toggling.
  - [ ] SuperAdmin role and security gate.

- [ ] **M7: Automated Verification & Isolation Assertions**
  - [ ] Automated tenant isolation test suite (`test_saas_isolation.py`).
  - [ ] Full regression check on AK Distributors data integrity in PostgreSQL.
