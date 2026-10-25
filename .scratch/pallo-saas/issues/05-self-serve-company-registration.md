# Self-Serve Company Registration and Provisioning

Type: prototype
Status: closed
Assignee: Antigravity
Blocked by: none (04 resolved)

## Question

How should the `/register` onboarding flow and [templates/register.html](file:///Users/hassaanjazz/Desktop/Projects/SaaS/Pallo/templates/register.html) be structured to collect business name, admin credentials, and currency, auto-generate a collision-proof URL slug (`apex-foods-2`), provision a default "Main Warehouse" and base categories, and automatically log the new user into their dashboard?

## Resolution

1. **Collision-Proof Slug Generation ([database.py](file:///Users/hassaanjazz/Desktop/Projects/SaaS/Pallo/database.py))**:
   - Implemented `generate_company_slug(name)`: Sanitizes business names into clean URL slugs and queries the database for existing matches. If a collision is encountered (e.g. `apex-foods`), appends `-2`, `-3`, etc., guaranteeing unique public URLs (`/c/<slug>/catalogue`).

2. **Atomic Tenant Provisioning ([database.py](file:///Users/hassaanjazz/Desktop/Projects/SaaS/Pallo/database.py))**:
   - Built `register_company_with_admin(...)`:
     - Creates new company record with currency, prefix, and active status.
     - Provisions a default `"Main Warehouse"` located at `"Headquarters"`.
     - Seeds standard starter categories (`General`, `Food`, `Beverages`, `Spices`, `Other`).
     - Provisions the root `admin` user associated with the new `company_id`.
     - Supports both PostgreSQL and SQLite fallback environments atomically.

3. **Self-Serve Onboarding UI ([templates/register.html](file:///Users/hassaanjazz/Desktop/Projects/SaaS/Pallo/templates/register.html))**:
   - Styled using Pallo's emerald (`#10b981`) and slate design tokens, ambient background grid, and Lucide icons.
   - Collects Business Name, Operating Currency (USD, PKR, AED, SAR, EUR, GBP, CAD), Admin Username, and Password with confirmation.
   - Includes feature checklist highlighting automated warehouse, category, and isolated partition provisioning.

4. **Registration Controller & Auto-Login ([app.py](file:///Users/hassaanjazz/Desktop/Projects/SaaS/Pallo/app.py))**:
   - Built `/register` route:
     - Validates input lengths and enforces global username uniqueness across the platform per ADR 0002.
     - Automatically logs the newly registered administrator in via `login_user(user_obj, remember=True)` upon successful provisioning.
     - Redirects the user directly to `/dashboard` with a welcome flash alert.
   - Added registration call-to-action on [templates/login.html](file:///Users/hassaanjazz/Desktop/Projects/SaaS/Pallo/templates/login.html) linking directly to `/register`.

5. **Automated Verification**:
   - Authored [tests/test_registration.py](file:///Users/hassaanjazz/Desktop/Projects/SaaS/Pallo/tests/test_registration.py) testing slug generation, collision avoidance, form validation (short names, duplicate usernames, password mismatches), and full registration flow. All 36 unit tests pass.
   - Live tested HTTP 200 responses on `http://127.0.0.1:5000/register`.
