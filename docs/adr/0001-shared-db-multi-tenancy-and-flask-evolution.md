# Shared Database Multi-Tenancy Architecture

We decided to convert the single-company ERP into a multi-tenant SaaS application (Pallo) using a single shared database partitioned by `company_id`, rather than a database-per-tenant architecture. This centralizes all platform operations, allows cross-tenant analytics and billing, enables single-step zero-downtime schema migrations, and unifies user management in a single SQLite/relational database.

## Considered Options

- **Database-per-Tenant (Isolated SQLite files)**: Provides complete physical data isolation and zero raw SQL query changes, but complicates cross-company analytics, unified authentication, global backups, and schema migrations across growing tenant counts.
- **Shared Database with `company_id` Partitioning (Selected)**: Aligns with industry standards (Salesforce `OrgID`, QuickBooks `RealmId`, Shopify `shop_id`), centralizing all data into `database.db`. Requires adding `company_id` to all entity tables and scoping all queries with `WHERE company_id = ?`.

## Consequences

- All entity tables (`users`, `customers`, `products`, `sales`, `sale_items`, `warehouses`, `suppliers`, `expenses`, `inventory_history`, `inventory_transfers`) must include a `company_id` foreign key.
- Existing data is assigned to `company_id = 1` ("AK Distributors LLC") to ensure 100% backward compatibility and zero operational downtime.
- Every read, write, and update query in `app.py` must enforce tenant scoping (`company_id = current_user.company_id`) to prevent data leakage.
