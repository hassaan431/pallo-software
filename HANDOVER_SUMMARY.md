# Project Handover & Progress Summary

This document serves as a comprehensive checkpoint for the **Inventory and Invoice Software** project to preserve context across sessions.

---

## 1. Tech Stack & Architecture
- **Backend Framework**: Python (Flask)
- **Database**: SQLite3 (`database.db`) with Foreign Keys enabled
- **Frontend**: HTML5, Vanilla CSS, Vanilla JavaScript (Jinja2 Templates)
- **Local Testing Server**: Launched via `python3 launch.py` on port `5000`
- **Deployment Platform**: PythonAnywhere (GitHub Repo: `hassaan431/ak-distributors-app`, branch `main`)

---

## 2. Key Rules & Workflows
1. **Local Testing First**: Always start local server via `python3 launch.py` so changes can be tested at `http://127.0.0.1:5000`.
2. **Restarting Server**: Whenever modifying backend (`app.py`, `database.py`) or templates, restart using `lsof -t -i :5000 | xargs kill -9 && python3 launch.py`.
3. **Deployment**: Commit code to GitHub (`git push origin main`), then user runs `git pull` & reloads web app in PythonAnywhere console.
4. **Main Inventory Template**: The `/inventory` route renders `inventory.html` (NOT `products.html`).

---

## 3. Work Completed Recently

### A. Date Added UI & Date Range Filtering
- **Modal Fields**: Added editable `<input type="date" name="created_at">` to both **Add Product** and **Edit Product** modals in `templates/inventory.html`.
- **Backend Persistence**: Updated `/inventory/add` and `/inventory/edit/<product_id>` routes in `app.py` to persist `created_at`.
- **Date Filtering**: Added `Date From` (`date_from`) and `Date To` (`date_to`) date picker filters next to the search bar in `templates/inventory.html` and handled filtering in `app.py` for `/inventory` and `/inventory/download_csv`.

### B. Inventory History (Stock Ledger System)
- **Database Schema**: Added `inventory_history` table in `database.py`:
  - Columns: `id`, `product_id`, `transaction_type` (`IN`, `OUT`, `ADJUSTMENT`), `quantity_change`, `previous_stock`, `new_stock`, `reference`, `created_at`.
- **Automatic Logging**:
  - `/inventory/add`: Logs `Initial Stock` or manual additions.
  - `/inventory/edit`: Checks old vs new stock and logs `IN` or `ADJUSTMENT`.
  - `/sales/new`, `/sales/update`, `/sales/delete`: Logs `OUT` when products are sold and `IN` when sales are edited/deleted.
- **API Endpoint**: Added `@app.route("/api/inventory_history/<int:product_id>")` to fetch stock ledger history as JSON.
- **UI Modal & History Button**: Added a **History** button next to "Edit" on the products table in `templates/inventory.html` which opens a modal fetching and displaying the history.
- **Data Backfill**: Executed a backfill script on the local database (`database.db`) to generate `Initial Stock (Legacy)` history entries for all existing products using their `created_at` dates.
- **Live Site Instructions**: Provided user with the Python snippet to execute in PythonAnywhere Bash console for live DB backfill.

### C. 4-Decimal Precision for Rates & Prices
- **Form Inputs**: Updated `step="0.0001"` for cost price, selling price, and invoice item rate input fields across `inventory.html`, `products.html`, and `sales.html`.
- **Smart Formatting**: Added `format_rate` Jinja filter and JS helper functions to dynamically display rates up to 4 decimal places (e.g. `$0.0022`) when sub-cent precision exists, while retaining standard 2 decimal places (e.g. `$5.00`) for standard prices.
- **PDF Invoices**: Updated `invoice_generator.py` to render 4-decimal rates accurately on generated PDF invoices and quotes.

---

## 4. Pending / Next Tasks
1. **Live Site Deployment Verification**: User to run `git pull`, reload app, and execute DB backfill script on PythonAnywhere.
2. **Bulk Product Import (CSV UI)**: Create a UI button in the Products page to import/bulk-update products via CSV.
3. **Hostinger VPS Migration (Optional/Future)**: Discussed potential migration from PythonAnywhere to Hostinger for native background jobs and better performance.

---

*End of Summary document.*
