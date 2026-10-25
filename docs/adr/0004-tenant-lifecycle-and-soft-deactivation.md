# Tenant Lifecycle and Soft-Deactivation Policy

We decided that tenant companies and user accounts will utilize soft-deactivation (`is_active = 0`) rather than physical deletion when an account is paused, suspended, or closed. In addition, an automated immutable database snapshot must precede the initial multi-tenant schema migration.

## Considered Options

- **Hard-Deletion (Cascade DELETE on Company)**: Completely purges company records. However, this causes unrecoverable data loss in dispute scenarios, violates commercial record-keeping compliance, and risks orphaned audit trails.
- **Soft-Deactivation (Selected)**: Sets `companies.is_active = 0`. All associated user sessions are terminated, and login attempts are intercepted with an informative inactive notice. Data remains intact for auditing or 1-click reactivation.

## Consequences

- All login and authentication middleware checks `company.is_active == 1` before admitting any session.
- Database backups are taken automatically before running migration scripts (`database_backup_pre_saas.db`).
