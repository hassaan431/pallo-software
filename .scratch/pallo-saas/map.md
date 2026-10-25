## Destination

A fully functional, production-ready Pallo multi-tenant SaaS running on PostgreSQL, where multiple independent businesses can self-register, manage multi-warehouse inventory, execute sales/POS, and generate custom-branded PDF invoices, with AK Distributors preserved as Company 1 with 100% data fidelity and zero cross-tenant leakage.

## Notes

- **Domain**: Wholesale & Retail ERP, Multi-Tenant SaaS, PostgreSQL, Flask/Python, Jinja2, ReportLab.
- **Skills to consult**: `domain-modeling`, `grilling`, `security-and-hardening`, `test-driven-development`, `dashboard-ui-charts`.
- **Standing preferences**: Preserve existing emerald (`#10b981`) & slate UI design tokens; zero breaking changes to AK Distributors; no data loss; strict commercial privacy for margins.
- **Issue Tracker**: Local Markdown tracker under `.scratch/pallo-saas/`.

## Decisions so far

- [Multi-tenancy Architecture](docs/adr/0001-shared-db-multi-tenancy-and-flask-evolution.md): Centralized single shared database partitioned by `company_id`.
- [Global User Identity](docs/adr/0002-global-user-identity-and-unified-auth.md): Globally unique credentials for zero-friction unified login (`/login`).
- [Role-Based Protection](docs/adr/0003-role-based-financial-and-cost-protection.md): Three standardized roles (`admin`, `salesman`, `warehouse_manager`) with sensitive supplier costs and profit margins strictly hidden from staff.
- [Tenant Lifecycle Policy](docs/adr/0004-tenant-lifecycle-and-soft-deactivation.md): Soft-deactivation (`is_active = 0`) on account pause/suspension, preserving tax and accounting audit records.
- [Database Engine Transition](docs/adr/0005-database-engine-transition-to-postgresql.md): Transition from SQLite to PostgreSQL with `ThreadedConnectionPool` and exact `NUMERIC` financial precision.
- [PostgreSQL Connection & Pooling](issues/01-provision-postgres-connection-and-pooling.md): Thread-safe `ThreadedConnectionPool` with `PooledConnectionWrapper` auto-returning connections and defaulting to `RealDictCursor`, driven by `DATABASE_URL` with SQLite fallback.
- [PostgreSQL Multi-Tenant Schema](issues/02-define-postgres-multi-tenant-schema.md): Complete DDL schema covering all 18 tables with `company_id` CASCADE FKs, `companies` master table, exact `NUMERIC(14, 4)` types, and composite performance indices.
- [SQLite to PostgreSQL Migration](issues/03-build-sqlite-to-postgres-migration-script.md): Standalone migration tool (`migrate_sqlite_to_postgres.py`) with topological sequencing, FK sanitization, sequence synchronization, and 100% parity verification.
- [Unified Auth & Tenant Context](issues/04-unified-auth-session-scoping-and-context.md): User model scoped by `company_id`, soft-deactivation session termination, and global template context injection (`current_company`, `app_name = 'Pallo'`).
- [Self-Serve Registration & Provisioning](issues/05-self-serve-company-registration.md): Collision-proof slug generator, atomic workspace initialization (warehouse, categories, admin user), and responsive `/register` onboarding flow.
- [Product & Inventory Scoping with Cost Masking](issues/06-scope-products-inventory-and-cost-masking.md): Multi-tenant isolation for products, categories, brands, and warehouse inventory; automated SQLite & Postgres compatibility with `PooledCursorWrapper`; ADR 0003 cost price and profit margin redaction for non-admin roles (`salesman`, `warehouse_manager`).
- [Customer & Sales POS Scoping with Tenant Sequential Invoicing](issues/07-scope-customers-and-sales-pos.md): Multi-tenant customer ledgers, sales CRUD, POS checkout, reports, dashboard isolation, quote conversion, dynamic invoice PDF branding, and company-specific sequential invoice numbers (e.g., AK-001012 vs INV-000001).
- [Warehouse Transfers, Purchases & Expenses Scoping](issues/08-scope-warehouses-transfers-purchases-expenses.md): Multi-tenant warehouse isolation and plan limits (`max_warehouses`); inter-warehouse transfer validation preventing cross-tenant stock movement; supplier ledger and purchase order scoping; admin-only operational expenses protection per ADR 0003; tenant staff management.
- [Dynamic PDF Invoicing & Company White-Label Settings](issues/09-dynamic-pdf-invoicing-and-company-branding.md): Dynamic white-labeling in sidebar (`templates/base.html`), Company Settings portal (`/settings/company`) with 2MB logo upload guardrails, and dynamic PDF invoice generation (`invoice_generator.py`) supporting tenant branding, custom currency symbols, and preserving AK Distributors dual logos.
- [SuperAdmin Platform Governance](issues/10-superadmin-platform-governance.md): SuperAdmin role and `@superadmin_required` gate, `/superadmin` metrics dashboard (total tenants, active/paused count, catalog products, GMV volume), 1-click tenant soft-deactivation toggle (`is_active = 0`) per ADR 0004 with login interception, master Company 1 protection, and tenant warehouse capacity updates.

## Not yet specified

- **Automated Cloud Backup & Point-in-Time Recovery**: S3/GCS automated WAL-archiving for automated daily tenant backups.
- **Billing & Stripe Integration**: Self-serve checkout portal and subscription webhook listeners when transitioning from free launch to paid tiers.
- **Custom Domains & White-label Vanity URLs**: Supporting custom DNS CNAME routing (`app.companyname.com`).
- **Multi-Currency Real-time FX Rates**: Dynamic currency exchange rate conversion if tenants trade across international borders.

## Out of scope

- **Database-per-Tenant Architecture**: Ruled out in ADR 0001 in favor of centralized PostgreSQL shared database.
- **Granular Custom Permission Matrix (Custom ACL)**: Ruled out in ADR 0003 in favor of three robust, opinionated roles.
- **Hard-Deletion of Tenant Accounts on Suspension**: Ruled out in ADR 0004 to preserve commercial compliance and audit integrity.
