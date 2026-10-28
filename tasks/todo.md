# Implementation Task List: Pallo SaaS UI Modernization, Branding & Unified Settings

## Phase 1: Brand Identity & Assets (Pallo Logo, Favicon & Brand Placement)

### Task 1: Generate High-Resolution Pallo Vector Logo & Favicons
**Description:** Create high-resolution SVG and PNG brand assets for Pallo SaaS, including the full horizontal brandmark with modern emerald-to-teal gradient typography, compact monogram mark for favicon/sidebar collapsed mode, and updated standard `favicon.ico` and `favicon.png` icons.
**Acceptance criteria:**
- [x] Official user-provided Pallo brandmark and mark cropped and saved to `static/logos/pallo_logo.png` and `static/logos/pallo_mark.png`.
- [x] `static/favicon.ico` and `static/favicon.png` generated and deployed with Pallo mark.
- [x] Dark mode inverted variants generated: `static/logos/pallo_logo_dark.png` and `static/logos/pallo_mark_dark.png`.
**Verification:**
- [x] Manual check: View files in browser to ensure clean rendering on light and dark backgrounds at multiple resolutions (16x16, 32x32, 192x192, full width).
**Dependencies:** None
**Files likely touched:**
- `static/logos/pallo_logo.png`
- `static/logos/pallo_mark.png`
- `static/logos/pallo_logo_dark.png`
- `static/logos/pallo_mark_dark.png`
- `static/favicon.ico`
- `static/favicon.png`
**Estimated scope:** Small (1-3 files)

---

### Task 2: Modernize Login & Registration Views with Pallo Branding
**Description:** Replace the legacy "AK Distributors LLC" and "Zain Foods" partner logo strip in `templates/login.html` and `templates/register.html` with the official Pallo SaaS logo, brand tagline, and updated favicon references. Ensure clean, modern SaaS auth layout.
**Acceptance criteria:**
- [x] `login.html` renders the Pallo SaaS brandmark and updated tagline ("Enterprise Distribution & Multi-Warehouse Operating System").
- [x] `register.html` and `login.html` link to the new Pallo favicons and titles.
- [x] Legacy partner strip is cleanly removed from the login screen.
**Verification:**
- [x] Manual check: Navigate to `/login` and `/register` in local browser to verify crisp branding, responsive card layout, and correct browser tab title/icon.
**Dependencies:** Task 1
**Files likely touched:**
- `templates/login.html`
- `templates/register.html`
**Estimated scope:** Small (2 files)

---

### Task 3: Update Main Application Panel & Base Template Branding
**Description:** Update `templates/base.html` and core application views to use Pallo as the default platform brand. If the active company has a custom uploaded logo, use the company's logo; otherwise, fall back to the Pallo brand mark. Update Cmd+K palette footer ("Pallo OS"), default `<title>` suffix, and generic modal title defaults.
**Acceptance criteria:**
- [x] Sidebar brand header displays tenant custom logo if uploaded, or Pallo logo/mark if no logo is uploaded.
- [x] Default `<title>` fallback uses `{{ current_company.name if current_company else 'Pallo' }}` across 20+ templates.
- [x] Cmd+K palette footer displays "Pallo OS" instead of "AK Portal".
- [x] Dashboard tour welcome popover references "Pallo" instead of hardcoded "AK Distributors".
**Verification:**
- [x] Manual check: Log into company 1 and a secondary tenant; verify sidebar header, browser tab title, and Cmd+K palette reflect expected branding.
**Dependencies:** Task 1
**Files likely touched:**
- `templates/base.html`
- `templates/dashboard.html`
- `templates/catalogue.html`
**Estimated scope:** Medium (3 files)

---

## Checkpoint: Brand Identity & Auth Verification
- [x] All tests pass: `pytest tests/test_saas_isolation.py` (7/7 passed)
- [x] Login, registration, and base application shell display Pallo brand mark and favicons.
- [x] Multi-tenant custom logo override functions without regression.

---

## Phase 2: Comprehensive Dark & Light Theme System

### Task 4: Design Token Architecture & Dark Palette in `style.css`
**Description:** Implement comprehensive dark theme variables in `static/css/style.css` using `[data-theme="dark"]`. Define dark values for canvas background, elevated card surfaces, borders, text hierarchies, input fields, selects, tables, zebra-striping, status pills, and shadows while preserving emerald brand accents.
**Acceptance criteria:**
- [x] `[data-theme="dark"]` CSS token rules are defined for `--color-canvas` (`#090d16`), `--color-surface` (`#111827`), `--color-sidebar` (`#0d1322`), `--color-border` (`#1e293b`), `--color-text` (`#f8fafc`), and `--color-text-muted` (`#94a3b8`).
- [x] Form controls (inputs, dropdowns, textareas, checkboxes) have high-contrast dark states with subtle border glow on focus.
- [x] Table headers, hover rows, and pagination controls render with crisp contrast in dark mode.
- [x] Print stylesheets (`@media print`) explicitly force white background and dark text.
**Verification:**
- [x] Manual check: Inspect CSS elements with DevTools, manually toggling `data-theme="dark"` on `<html>`.
**Dependencies:** None
**Files likely touched:**
- `static/css/style.css`
**Estimated scope:** Medium (1-2 files)

---

### Task 5: Theme Toggle Controller & Anti-FOUC Engine
**Description:** Build the JavaScript theme controller that persists user theme choice in `localStorage`, responds to OS `prefers-color-scheme`, and provides an anti-FOUC inline script in `<head>`. Add an interactive sun/moon toggle button in the top navigation bar with Lucide icons.
**Acceptance criteria:**
- [x] Inline script in `<head>` of `base.html` and `login.html` immediately applies `data-theme` before page render, eliminating flash of unstyled content.
- [x] Topbar features an accessible theme toggle button with sun/moon icon transition.
- [x] Toggling theme updates `localStorage.setItem('pallo_theme', ...)` and instantly switches the UI without page reload.
**Verification:**
- [x] Manual check: Click theme toggle in topbar; observe instant smooth transition between light and dark modes. Reload the page to ensure theme persists with zero flash.
**Dependencies:** Task 4
**Files likely touched:**
- `templates/base.html`
- `templates/login.html`
- `static/css/style.css`
**Estimated scope:** Small (2-3 files)

---

### Task 6: Element-Level Dark Mode Hardening & Chart Adaptability
**Description:** Audit and harden all complex components for dark mode: Universal Slide Drawer, Cmd+K Modal, Driver.js tour popover, POS Catalogue modal checkout, and Chart.js dynamic colors. Update Chart.js configuration in dashboard/reports to dynamically switch gridline and text colors based on the active theme.
**Acceptance criteria:**
- [x] Slide-drawer and Cmd+K modal backdrops and containers render seamlessly in dark mode.
- [x] Chart.js canvas elements use dark-compatible gridlines (`#1e293b`) and tick colors (`#94a3b8`) when dark mode is active.
- [x] Status pills and badges maintain clear, legible contrast across both modes.
**Verification:**
- [x] Manual check: Open Cmd+K palette, drawer, and view Dashboard charts in both dark and light modes; verify all text, borders, and graphs are crisp and easily readable.
**Dependencies:** Tasks 4, 5
**Files likely touched:**
- `templates/base.html`
- `templates/dashboard.html`
- `templates/reports.html`
- `static/css/style.css`
**Estimated scope:** Medium (3 files)

---

## Checkpoint: Theme System Verification
- [x] All tests pass: `pytest tests/test_saas_isolation.py` (7/7 passed)
- [x] Theme toggle smoothly switches between dark and light modes across all pages.
- [x] Contrast meets WCAG AA standards with no unreadable text or mismatched card borders.

---

## Phase 3: Unified Settings Hub (`/settings`)

### Task 7: Settings Hub Backend Route & Tab Controller (`app.py`)
**Description:** Implement a unified `@app.route('/settings', methods=['GET', 'POST'])` in `app.py` that consolidates settings management. Support tab switching (`?tab=company`, `?tab=users`, `?tab=brochure`, `?tab=preferences`, `?tab=platform`), handle updates with flash messages, enforce tenant query scoping, and maintain backward compatibility for existing `/settings/company` URLs.
**Acceptance criteria:**
- [x] Route `/settings` handles `GET` and `POST` for tenant settings with tab-aware navigation.
- [x] Sub-actions (updating company info, uploading logo, saving operational preferences) execute securely within `current_user.company_id`.
- [x] Existing route `/settings/company` delegates seamlessly to `/settings` with backward compatibility.
- [x] Platform tab is strictly forbidden to non-superadmin users.
**Verification:**
- [x] Tests pass: `pytest tests/test_saas_isolation.py` (8/8 passed)
- [x] Manual check: Navigate to `/settings` as regular admin and superadmin to verify data scoping.
**Dependencies:** None
**Files likely touched:**
- `app.py`
**Estimated scope:** Medium (1 file)

---

### Task 8: Unified Settings Hub Template (`templates/settings.html`)
**Description:** Create a cohesive, modern settings hub template with tabbed navigation sidebar and detailed settings panes:
1. **Company Profile & Branding**: Name, slug, currency, tax number, phone, address, and 2MB logo uploader with preview.
2. **Team & Users**: Inline user table with role badges, status indicators, and quick link/modal to add users.
3. **Brochure & Public Catalogue**: Brand compilation toggles, public catalog URL copy button, and safety caps.
4. **Operational Preferences**: Default warehouse, invoice prefix/starting sequence, low stock alert threshold, and default theme preference.
5. **Platform Governance (SuperAdmin only)**: Platform health link, soft-deactivation summary, and shortcut to superadmin console.
**Acceptance criteria:**
- [x] `templates/settings.html` provides clean desktop and mobile-responsive tabbed navigation.
- [x] Forms provide validation feedback and retain state on submission.
- [x] SuperAdmin tab only displays if `is_superadmin` is true.
**Verification:**
- [x] Manual check: Save changes across Company Profile, Brochure, and Preferences tabs; verify values persist in database and appear in invoices/catalog.
**Dependencies:** Task 7
**Files likely touched:**
- `templates/settings.html`
- `static/css/style.css`
**Estimated scope:** Medium (2 files)

---

### Task 9: Topbar & User Menu Navigation Integration
**Description:** Connect the new Settings Hub to the top navigation bar. Add a direct gear/settings icon button in `.topbar-right` and a prominent "Settings" option in `#userMenuDropdown`. Also update the sidebar Administration section to point directly to `/settings`.
**Acceptance criteria:**
- [x] Topbar has a dedicated Settings button (gear icon) with tooltip.
- [x] User menu dropdown has a clear "Settings" item linking to `/settings`.
- [x] Sidebar "Administration" menu links directly to `/settings` with active state highlighting.
**Verification:**
- [x] Manual check: Click Settings from topbar, user dropdown, and sidebar; confirm seamless navigation to `/settings`.
**Dependencies:** Tasks 7, 8
**Files likely touched:**
- `templates/base.html`
**Estimated scope:** Small (1 file)

---

## Checkpoint: Settings Hub & Platform End-to-End Test
- [x] All tests pass: `pytest tests/test_saas_isolation.py` (8/8 passed)
- [x] All tests pass: `pytest tests/` (78 passed, 1 skipped)
- [x] Settings hub opens from top menu, correctly switching between all tabs.
- [x] Dark and light mode renders settings forms, tabs, and tables with rich, harmonious aesthetics.

---

## Phase 4: SuperAdmin Tenant Switcher, Sidebar Branding & Inline User Directory

### Task 10: SuperAdmin Instant Tenant Switcher
**Description:** Implement session-based tenant context switching for superadmin users. Create `/superadmin/switch-tenant/<int:company_id>` endpoint (and clear route), allowing superadmins to view any company's dashboard, transactions, and inventory on the fly. Render an interactive, searchable Tenant Switcher in the topbar/sidebar visible only to superadmins.
**Acceptance criteria:**
- [x] `@app.route('/superadmin/switch-tenant/<int:company_id>', methods=['POST', 'GET'])` sets `session["active_company_id"]` with strict `@superadmin_required` verification.
- [x] Route `/superadmin/switch-tenant/clear` resets to default view.
- [x] Context processor and `load_user()` resolve `active_company_id` for superadmin requests without altering database user rows.
- [x] Topbar displays a polished "Viewing Workspace: [Company Name v]" switcher dropdown when superadmin is logged in.
**Verification:**
- [x] Tests pass: `pytest tests/test_superadmin_governance.py` (6/6 passed)
- [x] Manual check: Log in as superadmin, switch between Company 1 and other tenants; verify dashboard data changes dynamically.
**Dependencies:** None
**Files likely touched:**
- `app.py`
- `templates/base.html`
- `static/css/style.css`
**Estimated scope:** Medium (3 files)

---

### Task 11: Sidebar Header Identity Resolution & AK Logo Wiring
**Description:** Update the sidebar brand header so that superadmins always see "Pallo OS" with the Pallo Mark and `SUPERADMIN` badge, while client workspaces see their own company name and custom logo. Wire Company 1 ("AK Distributors LLC") in the database to use its authentic logo file `static/logos/AK_Distributors_Logo.png`.
**Acceptance criteria:**
- [x] When logged in as SuperAdmin in platform overview, the sidebar header displays the Pallo brand mark and title "Pallo OS" with badge `SUPERADMIN`. When an active tenant is switched, it indicates the active tenant with `SUPERADMIN` badge.
- [x] When logged in as a Client Tenant, the sidebar header displays their company name, their uploaded logo (or Pallo mark fallback), and badge `WORKSPACE`.
- [x] Database migration/init ensures Company 1 ("AK Distributors LLC") has `logo_url = '/static/logos/AK_Distributors_Logo.png'` so AK Distributors uses its authentic branding.
**Verification:**
- [x] Manual check: Log into superadmin, verify "Pallo OS" displays. Log into Company 1, verify AK Distributors logo displays.
**Dependencies:** Task 10
**Files likely touched:**
- `templates/base.html`
- `database.py`
**Estimated scope:** Small (2 files)

---

### Task 12: Inline User Management in Settings Hub (Team & Users Tab)
**Description:** Embed full user management directly within the Settings Hub (`templates/settings.html` Tab 2) so admins don't need to leave the page. Provide `+ Add User` modal, inline edit role/warehouse modal, password reset modal, and one-click active/suspended status toggle directly in the table.
**Acceptance criteria:**
- [x] "Manage Full User Directory" external link replaced with inline `+ Add Team Member` button opening a modern modal on the page.
- [x] Each user table row has quick action buttons: Edit User (Role & Warehouse), Reset Password, and Suspend/Activate toggle.
- [x] Backend routes `/users/add`, `/users/edit/<id>`, `/users/reset_password`, `/users/toggle_active/<id>` support redirecting to `/settings?tab=users` when referred from settings and return JSON where appropriate.
- [x] Multi-tenant isolation is strictly preserved (admins cannot add or modify users outside their company).
**Verification:**
- [x] Tests pass: `pytest tests/test_superadmin_governance.py` (6/6 passed)
- [x] Manual check: Add a user, edit their role, reset password, and toggle active status directly inside Settings Hub Tab 2 without leaving the tab.
**Dependencies:** None
**Files likely touched:**
- `templates/settings.html`
- `app.py`
- `static/css/style.css`
**Estimated scope:** Medium (3 files)

---

## Checkpoint: SuperAdmin Switcher & Inline Users Verification
- [x] All tests pass: `pytest tests/test_superadmin_governance.py` (6/6 passed)
- [x] All tests pass: `pytest tests/` (80 passed, 1 skipped)
- [x] SuperAdmin can switch between tenants and view their isolated data instantly.
- [x] Sidebar header displays "Pallo OS" for SuperAdmin and correct tenant branding for clients.
- [x] Team & Users tab in Settings Hub provides full end-to-end user administration on the spot.
- [ ] User confirms verification before git commit and push.
