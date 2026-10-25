# Unified Authentication, Session Scoping and Company Context

Type: task
Status: closed
Assignee: Antigravity
Blocked by: none (03 resolved)

## Question

How do we adapt the Flask-Login `User` model, session deserialization, and `@app.context_processor` in [app.py](file:///Users/hassaanjazz/Desktop/Projects/SaaS/Pallo/app.py) so that entering credentials on the unified `/login` page immediately resolves the user to their `company_id`, enforces soft-deactivation checks (`company.is_active == 1`), and injects `current_company` into all Jinja2 templates?

## Resolution

1. **User Model & Session Scoping ([app.py](file:///Users/hassaanjazz/Desktop/Projects/SaaS/Pallo/app.py))**:
   - Extended `User` model with `company_id: int = 1`, making tenant context an intrinsic property of the authenticated user session.
   - Refactored `load_user(user_id)` to resolve `company_id`, verify user `is_active`, and verify `company.is_active` (soft-deactivation policy per ADR 0004). Superadmins bypass tenant deactivation so platform operators can manage accounts.

2. **Company Retrieval Helper ([database.py](file:///Users/hassaanjazz/Desktop/Projects/SaaS/Pallo/database.py))**:
   - Added `get_company(company_id)` to query the `companies` table using query parameter abstraction (`%s` on PostgreSQL, `?` on SQLite).
   - Provided built-in fallback metadata for Company 1 ("AK Distributors LLC") to ensure flawless operation during migration and in local SQLite fallback modes.
   - Enhanced `get_user_by_id()` and `get_user_by_username()` to select and return `company_id` (defaulting to 1 when unset).

3. **Global Multi-Tenant Context Processor ([app.py](file:///Users/hassaanjazz/Desktop/Projects/SaaS/Pallo/app.py))**:
   - Implemented `@app.context_processor` (`inject_pallo_context()`):
     - Injects `current_company` dict (`name`, `slug`, `currency`, `invoice_prefix`, `logo_url`, `is_active`) across all Jinja2 templates.
     - Injects global platform brand token `app_name = 'Pallo'`.
     - Injects boolean flag `is_superadmin = (current_user.role == 'superadmin')`.

4. **Access Control Decorators ([app.py](file:///Users/hassaanjazz/Desktop/Projects/SaaS/Pallo/app.py))**:
   - Added `superadmin_required`: Restricts platform routes strictly to `superadmin` role.
   - Added `company_admin_required`: Admits both `admin` and `superadmin` roles while blocking non-admin staff (`salesman`, `warehouse_manager`).
   - Updated `admin_required` to allow superadmin traversal.

5. **Unified Sign-in & Soft-Deactivation Interception ([app.py](file:///Users/hassaanjazz/Desktop/Projects/SaaS/Pallo/app.py))**:
   - Updated `/login` to globally authenticate credentials per ADR 0002 without requiring a tenant subdomain or code.
   - Intercepts deactivated user accounts ("Account is disabled. Please contact the administrator.").
   - Intercepts users whose company has been paused/suspended per ADR 0004 ("Your company account has been paused or suspended. Please contact support.").
   - Resolves `company_id` into the session and routes superadmin to platform management, salesmen to POS, and admins to dashboard.

6. **Automated Verification**:
   - Authored unit test suite [tests/test_auth_scoping.py](file:///Users/hassaanjazz/Desktop/Projects/SaaS/Pallo/tests/test_auth_scoping.py) covering user model scoping, company lookup fallback, session loading, company soft-deactivation enforcement, superadmin bypass, context processor injection, and login interception. All 29 unit tests pass cleanly.
