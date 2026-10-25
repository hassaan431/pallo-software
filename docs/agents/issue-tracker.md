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

- [x] **M1: PostgreSQL Setup, Schema Creation & Data Migration**
  - [x] Add `psycopg2-binary` and `python-dotenv` to dependencies.
  - [x] Configure `DATABASE_URL` connection management with `ThreadedConnectionPool`.
  - [x] Build PostgreSQL multi-tenant schema with `company_id`, exact `NUMERIC` types, and composite indices.
  - [x] Write and run `migrate_sqlite_to_postgres.py` to transfer 100% of AK Distributors data to `company_id = 1`.
  - [x] Add query helpers in `database.py` with `RealDictCursor`.

- [x] **M2: Authentication, Tenant Scoping & Self-Serve Signup**
  - [x] Extend Flask-Login `User` with `company_id`.
  - [x] Implement `@app.context_processor` for `current_company`.
  - [x] Create `/register` self-serve onboarding page with auto-slug generation.
  - [x] Seed default "Main Warehouse" and starter categories for newly registered companies.
  - [x] Update `/login` for unified sign-in with active company validation.

- [x] **M3: Query Scoping & Commercial Privacy (app.py)**
  - [x] Scope Products, Categories, Brands (`company_id`). Mask `cost_price` for non-admins.
  - [x] Scope Customers & Ledgers (`company_id`).
  - [x] Scope Sales, POS, and Invoices (`company_id`).
  - [x] Scope Warehouses & Inventory Transfers (`company_id`).
  - [x] Scope Purchases & Suppliers (`company_id`).
  - [x] Scope Expenses & Financial Reports (`company_id`, admin-only).
  - [x] Scope User/Staff Management (`company_id`).

- [x] **M4: Dynamic White-Labeling & Invoicing**
  - [x] Dynamic invoice PDF generation (`invoice_generator.py`) based on company settings (preserving AK Distributors formatting for Company 1).
  - [x] Company profile & branding settings page (`/settings/company`) with 2MB logo upload guardrails.
  - [x] Dynamic sidebar branding and company name badge.

- [x] **M5: Public Tenant Catalogues & Resource Guardrails**
  - [x] Implement `/c/<company_slug>/catalogue` and `/c/<company_slug>/brochure`.
  - [x] Keep root `/catalogue` and `/brochure` backwards compatible to Company 1.
  - [x] Apply 250-item safety cap on brochure PDF exports.

- [x] **M6: SuperAdmin Platform Management**
  - [x] Build `/superadmin` dashboard for platform metrics and soft-deactivation toggling.
  - [x] SuperAdmin role and security gate.

- [x] **M7: Automated Verification & Isolation Assertions**
  - [x] Automated tenant isolation test suite (`test_saas_isolation.py`).
  - [x] Full regression check on AK Distributors data integrity in PostgreSQL.
