# SuperAdmin Platform Governance Dashboard

Type: prototype
Status: closed
Blocked by: none (04 resolved)

## Question

How should the `/superadmin` dashboard and [templates/superadmin.html](file:///Users/hassaanjazz/Desktop/Projects/SaaS/Pallo/templates/superadmin.html) be constructed to display platform-wide metrics (total companies, total products, aggregate sales GMV) and provide a 1-click soft-deactivation toggle (`is_active = 0`) to manage tenant access?

## Resolution

1. **SuperAdmin Security Gate (`@superadmin_required`)**:
   - Enforced role check requiring `current_user.role == 'superadmin'` across all platform-level governance endpoints.
   - Non-superadmin users attempting direct access are redirected to their authorized workspaces.

2. **Platform Governance Dashboard (`/superadmin`)**:
   - Built route in `app.py` aggregating platform-wide KPIs:
     - Total registered business tenants (active vs paused counts).
     - Platform-wide sales GMV and order transactions volume.
     - Total catalog products across all tenant catalogs.
     - Total platform staff and admin accounts.
   - Designed responsive workstation UI in `templates/superadmin.html` with tabular breakdown of tenants, footprint statistics (users, products, sales, GMV), plan capacity controls, and lifecycle status.

3. **1-Click Tenant Soft-Deactivation (`/superadmin/company/<id>/toggle_status`)**:
   - Implemented toggle updating `companies.is_active` (1 <-> 0).
   - Per ADR 0004, deactivating a tenant immediately intercepts subsequent login attempts with an informative inactive notice while preserving all financial ledgers, audit trails, and inventory history.
   - Protected Master Company 1 ("AK Distributors LLC") with strict rejection against deactivation.

4. **Plan Capacity Management (`/superadmin/company/<id>/update_plan`)**:
   - Added endpoint allowing platform operators to adjust `max_warehouses` for any tenant.

5. **Navigation & White-Labeling Integration**:
   - Updated `templates/base.html` to display the "Platform Console" navigation item and `SUPERADMIN` badge for superadmin sessions.

6. **Automated Verification**:
   - Created test suite `tests/test_superadmin_governance.py` with 4 test scenarios passing cleanly (67 total passing tests across the project).
