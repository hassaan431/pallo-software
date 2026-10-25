# Dynamic PDF Invoicing and Company White-Label Settings

Type: prototype
Status: closed
Blocked by: none (07 resolved)

## Question

How should [invoice_generator.py](file:///Users/hassaanjazz/Desktop/Projects/SaaS/Pallo/invoice_generator.py) dynamically render company logos, legal names, addresses, and tax numbers (preserving dual AK + Zain logos for Company 1), and how should `/settings/company` handle logo uploads with 2MB validation and disk safety guardrails?

## Resolution

1. **Company Profile & Branding Settings (`/settings/company`)**:
   - Built GET and POST routes in `app.py` protected by `@login_required` and `@admin_required`.
   - Allows tenant admins to update legal name, tax/VAT ID, billing address, shipping address, contact phone, contact email, regional currency symbol, and invoice prefix.
   - Enforces 2MB maximum upload size cap and restricts extensions to `.png`, `.jpg`, `.jpeg`, `.webp`, and `.svg`.
   - Safely saves logos into `static/logos/companies/company_{cid}.{ext}` with support for logo removal.

2. **White-Label Sidebar & Header Navigation (`templates/base.html`)**:
   - Updated sidebar brand header to dynamically render tenant's uploaded logo (`current_company.logo_url`), fallback monogram (`current_company.name[:2]`), and plan badge (`PORTAL` for AK Distributors, `PRO` for tenant workspaces).
   - Preserves AK Distributors dual logos and branding for Company 1.
   - Added "Company Settings" navigation link under the Administration sidebar section.

3. **Dynamic Invoice PDF Generator (`invoice_generator.py`)**:
   - Preserved dual AK Distributors & Zain Foods logos and Sacramento contact details for Company 1.
   - Dynamically renders custom logo, monogram, business legal name, billing address, phone, email, and tax ID for tenant companies.
   - Dynamically formats all monetary totals, item rates, discounts, amounts paid, and remaining balances using the company's designated currency symbol.

4. **Testing & Verification**:
   - Added `tests/test_company_branding_settings.py` covering 7 test scenarios (access control, updating fields, required name validation, valid upload, extension rejection, 2MB size limit rejection, and PDF generation).
   - All 63 tests in repository pass with 100% green status.
