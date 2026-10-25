# Global User Credential Uniqueness and Identity Resolution

We decided that user credentials (`username` and `email`) must be globally unique across all of Pallo, rather than unique only within a single tenant company. This allows a unified `/login` portal where entering credentials immediately resolves the user to their specific company workspace without requiring a workspace slug or organization selector.

## Considered Options

- **Tenant-Scoped Usernames (Duplicate allowed across companies)**: Allows two different companies to both have a user named `salesman`. However, this requires users to first identify their company (via subdomain `company.pallo.app` or a two-step login entering company code first).
- **Globally Unique Credentials (Selected)**: Users sign in through a single unified form (`/login`). The system looks up the user account globally, determines their `company_id` and role, and scopes their session immediately.

## Consequences

- The `users` table enforces a global `UNIQUE(username)` (and `UNIQUE(email)` when provided).
- A dedicated `superadmin` role is created for platform governance, while company staff accounts are scoped to their respective `company_id`.
- Staff invitations or account creations within a company must validate against global username availability.
