# Implementation Plan: Pallo SaaS UI Modernization, Branding & Unified Settings Hub

## Overview

This implementation plan covers three core enhancements requested for the Pallo SaaS platform:
1. **Pallo Brand Identity Replacement**: Replacing legacy "AK Distributors" logos, titles, and partner strips across the main application panel, login page, registration flow, Cmd+K palette, and favicons with polished, high-resolution Pallo SVG/PNG vector branding.
2. **Comprehensive Dark & Light Mode System**: Implementing a seamless, zero-flash (anti-FOUC) theme switcher with an accessible toggle in the top navigation. The design tokens will provide balanced contrast, sleek slate/emerald aesthetics, and complete styling across cards, data tables, form controls, modals, slide-drawers, and Chart.js visualizations.
3. **Unified Settings Hub (`/settings`)**: Creating a centralized, modern settings page accessible directly from the top menu, featuring tabbed management for Company Profile & Branding, Team/User Management, Brochure & Catalogue Settings, Operational Preferences, and SuperAdmin Platform Controls (role-gated).

---

## Architecture Decisions

- **ADR-Style Decisions**:
  - **Zero-FOUC Theme Script**: Place a lightweight blocking script in the `<head>` of `base.html` and standalone auth templates that parses `localStorage.getItem('pallo_theme')` and OS `prefers-color-scheme`, immediately applying `data-theme="dark"` or `data-theme="light"` to the `<html>` root before DOM paint.
  - **CSS Custom Property Tokens**: Expand `:root` and `[data-theme="dark"]` in `static/css/style.css` so all components (surfaces, inputs, dropdowns, table striping, borders, pills, and chart gridlines) adapt automatically via semantic CSS tokens (`--color-canvas`, `--color-surface`, `--color-border`, `--color-text`, `--color-text-muted`, etc.).
  - **Dynamic Logo Fallback Hierarchy**: In `base.html`, if the logged-in company has an uploaded custom logo (`current_company.logo_url`), display the company's logo; if not, or on platform-level pages (login, registration, superadmin console), display the official Pallo SaaS brand logo.
  - **Unified Settings Routing**: Consolidate settings navigation under `/settings` with a clean tabbed interface (`/settings?tab=company`, `users`, `brochure`, `preferences`, `platform`) while preserving backward-compatibility for existing bookmarks (`/settings/company` redirects cleanly to `/settings?tab=company`).
  - **Security & Multi-Tenant Scoping**: All settings tabs strictly respect tenant isolation (`company_id = current_user.company_id`), with the Platform / Governance tab strictly gated to `is_superadmin` users.

---

## Task List

### Phase 1: Brand Identity & Assets (Pallo Logo, Favicon & Brand Placement)
- [ ] **Task 1: Generate High-Resolution Pallo Vector Logo & Favicons**
  - Create modern SVG vector logo with emerald-to-teal gradients and clean geometric typography for Pallo SaaS.
  - Generate matching PNG logos and crisp multi-size favicons (`static/favicon.ico`, `static/favicon.png`, `static/logos/pallo_logo.svg`, `static/logos/pallo_logo.png`, `static/logos/pallo_mark.svg`).
- [ ] **Task 2: Modernize Login & Registration Views with Pallo Branding**
  - Replace AK Distributors & Zain Foods dual partner strip in `templates/login.html` with the modern Pallo brand hero and product tagline.
  - Update page title, favicon links, and register link labels in `login.html` and `register.html`.
- [ ] **Task 3: Update Main Application Panel & Base Template Branding**
  - Update `templates/base.html`: sidebar brand fallback logo, title tag defaults, Cmd+K palette footer ("Pallo OS" instead of "AK Portal"), and details drawer title fallbacks.
  - Audit titles and brand mentions in `templates/dashboard.html` and other templates.

### Checkpoint: Brand Identity & Auth Verification
- [ ] Inspect login page, registration page, and main dashboard locally. Verify favicons load crisp and brand identity is consistently "Pallo" with company logo overrides working properly.

---

### Phase 2: Comprehensive Dark & Light Theme System
- [ ] **Task 4: Design Token Architecture & Dark Palette in `style.css`**
  - Define full `[data-theme="dark"]` variable set in `static/css/style.css` (canvas `#0b0f19`, elevated surface `#131b2e`, borders `#1e293b`, muted text `#94a3b8`, primary glow `#10b981`).
  - Style dark mode states for inputs, selects, tables, zebra-striping, status badges, dropdowns, and dialog backdrops.
- [ ] **Task 5: Theme Toggle Controller & Anti-FOUC Engine**
  - Add inline head script in `templates/base.html` and `templates/login.html` to prevent theme flash.
  - Add a sleek Sun/Moon icon toggle button in the topbar (`.topbar-right`).
  - Wire up Alpine/vanilla JS event listeners to toggle `data-theme` on `<html>`, persist selection to `localStorage`, and trigger smooth icon transition.
- [ ] **Task 6: Element-Level Dark Mode Hardening & Chart Adaptability**
  - Harden specific elements: Universal Slide Drawer, Cmd+K Modal, Driver.js product tour, invoice previews, and print stylesheets (`@media print` forced light mode).
  - Update Chart.js global defaults or theme hook to render legible axis labels, gridlines (`#1e293b`), and tooltip surfaces in dark mode.

### Checkpoint: Theme System Verification
- [ ] Test toggle across light and dark modes on multiple pages (Dashboard, Inventory, Sales, Reports, POS). Verify zero visual artifacts, high contrast readability, and instant persistence across page reloads.

---

### Phase 3: Unified Settings Hub (`/settings`)
- [ ] **Task 7: Settings Hub Backend Route & Tab Controller (`app.py`)**
  - Create `@app.route('/settings', methods=['GET', 'POST'])` handling active tabs: `company`, `users`, `brochure`, `preferences`, and `platform`.
  - Maintain backward compatibility redirect from `/settings/company` to `/settings?tab=company`.
  - Load relevant scoped data: company profile, tenant users, brochure brand selection, and company operational preferences.
- [ ] **Task 8: Unified Settings Hub Template (`templates/settings.html`)**
  - Build responsive settings interface with sticky navigation tabs (Company, Users, Brochure, Preferences, Platform).
  - Integrate Company Profile form with logo upload (2MB safety cap).
  - Integrate Team Management sub-view with user listing and role badges.
  - Integrate Brochure Settings sub-view with public catalog toggles and URL copier.
  - Add Client Operational Preferences (default warehouse, low stock alert threshold, invoice prefix, default theme preference).
  - Include SuperAdmin Platform section (visible only to `is_superadmin`) linking to platform metrics and soft-deactivation controls.
- [ ] **Task 9: Topbar & User Menu Navigation Integration**
  - Add a direct Settings shortcut icon and link in the topbar and inside `#userMenuDropdown` in `templates/base.html`.
  - Ensure mobile drawer navigation also includes direct access to Settings.

### Checkpoint: Settings Hub & Platform End-to-End Test
- [x] All tests pass: `pytest tests/test_saas_isolation.py` (8/8 passed)
- [x] All tests pass: `pytest tests/` (78 passed, 1 skipped)
- [x] Settings hub opens from top menu, switching seamlessly between all tabs.
- [x] Dark and light mode renders settings forms, tabs, and tables with rich, harmonious aesthetics.

---

### Phase 4: SuperAdmin Tenant Switcher, Sidebar Branding & Inline User Directory

- [ ] **Task 10: Instant Tenant Switcher for SuperAdmin (`app.py` & `base.html`)**
  - Implement session-driven company switching for superadmin accounts via `@app.route('/superadmin/switch-tenant/<int:company_id>')`.
  - Allow superadmins to switch between viewing any client tenant's data (or return to default platform overview).
  - Add a sleek, interactive Tenant Switcher dropdown in the top header / sidebar visible exclusively to superadmins.
- [ ] **Task 11: Sidebar Header Identity Resolution (`base.html` & database)**
  - For SuperAdmin: display the Pallo Mark with title **"Pallo OS"** (or **"Pallo OS · [Tenant Name]"** when switched) and badge `SUPERADMIN`, instead of showing Company 1's title.
  - Wire Company 1 ("AK Distributors LLC") to its authentic `static/logos/AK_Distributors_Logo.png` so AK Distributors displays its own logo when viewed.
  - For Client Tenants: display their custom company logo (or Pallo fallback if not yet uploaded) with their company name and badge `WORKSPACE`.
- [ ] **Task 12: Inline User Management in Settings Hub (`templates/settings.html` & `app.py`)**
  - Remove the external "Manage Full User Directory" redirect button.
  - Embed full user management directly within **Settings Hub → Team & Users**:
    - `+ Add User` button opening modal with username, role, password, and assigned warehouse.
    - Inline table action buttons for each user: Edit Role/Warehouse modal, Reset Password modal, and instant Active/Suspended status toggle.
    - Form action endpoints redirecting back to `/settings?tab=users` with flash messages.

### Checkpoint: SuperAdmin Switcher & Inline Users Verification
- [ ] SuperAdmin can switch to any tenant and see that tenant's dashboard, inventory, and sales.
- [ ] Sidebar header correctly displays "Pallo OS" for SuperAdmin and tenant name/logo for clients.
- [ ] Add, edit, password reset, and suspend/reactivate work directly inside Settings Hub Team & Users tab.
- [ ] Full test suite passes: `pytest tests/` (all 78+ tests green).

---

## Risks and Mitigations

| Risk | Impact | Mitigation |
|------|--------|------------|
| Tenant switcher leaks cross-tenant session state to non-superadmin users | High | Strict `@superadmin_required` check on switch endpoint; session override only honored if `current_user.role == 'superadmin'`. |
| Inline user management form collision with Settings Hub main forms | Med | Use independent modals with distinct form IDs and explicit action URLs (`/users/add`, `/users/edit`, etc.). |
| Database transaction abort on multi-tenant tests | Low | Always guard database engine differences (PostgreSQL vs SQLite) with clean rollbacks. |
