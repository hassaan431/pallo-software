# Pallo Multi-Tenant SaaS — Production Deployment & Cutover Plan

## Overview
This document serves as the master deployment guide and handoff prompt for transitioning **Pallo Multi-Tenant SaaS** (formerly single-tenant wholesale ERP "AK Distributors LLC") from the local development SQLite environment to a live, multi-tenant production environment backed by **PostgreSQL**.

- **Repository**: `hassaan431/ak-distributors-app` (branch: `main`, latest commit: `2e86253`)
- **Core Stack**: Flask (Python 3.10+), PostgreSQL (with `psycopg2-binary` & `ThreadedConnectionPool`), Flask-Login, Jinja2, ReportLab, Vanilla CSS.
- **Current Test Status**: 74 / 74 tests passing (`pytest tests/ -v`).
- **Master Tenant**: Company ID `1` ("AK Distributors LLC", slug: `ak-distributors`) with 100% data fidelity preserved.

---

## 1. Architectural Readiness Checklist

| Milestone | Component | Production Status |
|:---|:---|:---|
| **M1** | PostgreSQL Pool & Schema | Ready (`schema_postgres.sql`, `ThreadedConnectionPool` with fallback) |
| **M1** | SQLite to PostgreSQL Migration | Ready (`migrate_sqlite_to_postgres.py` with `--dry-run` & sequence sync) |
| **M2** | Multi-Tenant Auth & Onboarding | Ready (`/register`, `/login`, active company session validation) |
| **M3** | Query Scoping & Cost Masking | Ready (ADR 0003 margin & cost protection for non-admin staff) |
| **M4** | White-Labeling & Dynamic Invoices | Ready (`/settings/company`, 2MB logo upload, ReportLab dynamic PDFs) |
| **M5** | Public Catalogues & Brochures | Ready (`/c/<slug>/catalogue`, `/c/<slug>/brochure`, 250-item PDF safety cap) |
| **M6** | SuperAdmin Platform Governance | Ready (`/superadmin`, platform metrics, soft-deactivation toggle ADR 0004) |
| **M7** | Automated Tenant Isolation | Ready (`tests/test_saas_isolation.py`, 74 total passing tests) |

---

## 2. Production Deployment Architecture Options

### Option A: PythonAnywhere (Recommended for Current Setup)
- **Web App Host**: PythonAnywhere WSGI configuration pointing to `app:app`.
- **Database**:
  - *Option A1 (Managed External PostgreSQL)*: Neon.tech, Supabase, AWS RDS, or Render PostgreSQL (provides pooling, SSL, and automated backups).
  - *Option A2 (PythonAnywhere Postgres Add-on)*: Built-in PythonAnywhere PostgreSQL database instance.
- **Static & Media Files**: PythonAnywhere static file mapping for `/static/` and `/static/logos/`.

### Option B: Modern Cloud Container / VPS (Render, Railway, Fly.io, DigitalOcean)
- **Container / Service**: Gunicorn WSGI (`gunicorn -w 4 -b 0.0.0.0:5000 app:app`).
- **Database**: Dedicated PostgreSQL 15+ database instance.
- **Volume Storage**: Persistent disk mounted for `static/logos/companies/`.

---

## 3. Step-by-Step Deployment Runbook

### Phase 1: Environment & Dependency Preparation
1. **Pull Latest Code**:
   ```bash
   cd ~/ak-distributors-app  # or your deployment directory
   git checkout main
   git pull origin main
   ```
2. **Install / Update Dependencies**:
   ```bash
   source venv/bin/activate  # activate your production virtualenv
   pip install -r requirements.txt
   ```
   *Ensures `psycopg2-binary` and `python-dotenv` are installed.*

3. **Configure Environment Variables (`.env`)**:
   Create or update `.env` in the project root:
   ```env
   # PostgreSQL Connection String (Required for multi-tenant Postgres mode)
   DATABASE_URL=postgresql://<user>:<password>@<host>:5432/<dbname>?sslmode=require

   # Connection Pool Capacity
   DB_POOL_MIN=2
   DB_POOL_MAX=20

   # Flask Security
   SECRET_KEY=<generate-strong-random-key>
   FLASK_ENV=production
   ```
   *(Note: If `DATABASE_URL` is omitted, the app safely defaults to local SQLite `database.db`)*.

---

### Phase 2: PostgreSQL Schema Provisioning & Data Migration
1. **Initialize Multi-Tenant Schema**:
   Run schema initialization into your PostgreSQL database:
   ```bash
   python3 -c "from database import init_postgres_db, get_database_url; init_postgres_db(get_database_url()); print('Postgres schema successfully initialized!')"
   ```
   *This creates all 19 relational tables, foreign keys with `ON DELETE CASCADE`, composite indices, and default constraints from `schema_postgres.sql`.*

2. **Execute Data Migration in Dry-Run Mode**:
   Before committing live data, execute a non-destructive dry-run to verify row-count parity and foreign key integrity:
   ```bash
   python3 migrate_sqlite_to_postgres.py --dry-run
   ```
   *Review the verification table output to confirm all tables report `PASSED`.*

3. **Execute Live Production Migration**:
   ```bash
   python3 migrate_sqlite_to_postgres.py
   ```
   *This securely transfers 100% of AK Distributors data into `company_id = 1`, creates the Master Company record, resets all auto-increment sequences, and commits the transaction.*

---

### Phase 3: SuperAdmin Account Setup
To manage the multi-tenant platform via the `/superadmin` governance dashboard, provision or designate a SuperAdmin user:
```bash
python3 -c "
from database import get_connection
from werkzeug.security import generate_password_hash

conn = get_connection()
username = 'superadmin'
password = '<CHOOSE_STRONG_PASSWORD>'
pw_hash = generate_password_hash(password, method='pbkdf2:sha256')

# Insert or upgrade existing user to superadmin
existing = conn.execute('SELECT id FROM users WHERE username = ?', (username,)).fetchone()
if existing:
    conn.execute('UPDATE users SET role = \'superadmin\' WHERE username = ?', (username,))
    print(f'User {username} upgraded to SuperAdmin!')
else:
    conn.execute('INSERT INTO users (username, password_hash, role, company_id) VALUES (?, ?, \'superadmin\', 1)', (username, pw_hash))
    print(f'SuperAdmin user {username} created!')
if hasattr(conn, 'commit'): conn.commit()
if hasattr(conn, 'close'): conn.close()
"
```

---

### Phase 4: WSGI Web Server Cutover & Reload
1. **PythonAnywhere Web Tab**:
   - Verify Virtualenv path points to the active virtualenv.
   - Set environment variables in the WSGI configuration file (`/var/www/<username>_pythonanywhere_com_wsgi.py`):
     ```python
     import os
     from dotenv import load_dotenv
     project_folder = os.path.expanduser('~/ak-distributors-app')
     load_dotenv(os.path.join(project_folder, '.env'))
     ```
   - Set Static Files mappings:
     - Directory: `~/ak-distributors-app/static/` -> URL: `/static/`
   - Click **"Reload <username>.pythonanywhere.com"**.

---

### Phase 5: Post-Deployment Smoke Verification Checklist
Perform these checks immediately after reloading:
- [ ] **AK Distributors Access**: Log in as `admin` on `/login`. Verify dashboard KPIs, products catalog, customer list, and existing orders appear identical to pre-migration state.
- [ ] **Branding & Dual Logos**: View an existing invoice PDF preview. Verify Company 1 dual logos and contact info are preserved.
- [ ] **Self-Serve Onboarding**: Open incognito tab and navigate to `/register`. Register a new test company (`Beta Wholesale LLC`). Verify auto-redirect to `/login` and atomic provisioning of warehouse and starter categories.
- [ ] **Commercial Privacy**: Log in as a salesman user. Verify product cost prices and profit margins are completely hidden across `/products`, `/pos`, and CSV downloads.
- [ ] **Public Catalogue**: Open `/c/ak-distributors/catalogue` and `/c/ak-distributors/brochure` in public browser. Verify catalog loads without authentication.
- [ ] **SuperAdmin Governance**: Log in as the SuperAdmin user and navigate to `/superadmin`. Verify platform metrics display active tenant counts and GMV totals.
- [ ] **Audit Logs & Status**: Verify no connection pool exhaustion or unhandled exceptions appear in server error logs.

---

### Phase 6: Rollback Plan (Zero-Risk Fallback)
If unexpected issues arise during live cutover:
1. In `.env`, comment out `DATABASE_URL=` (or set it empty).
2. Reload the web app.
3. The application will immediately and automatically fallback to the local SQLite `database.db` engine without data modification or loss.

---

# 🤖 Agent Handoff Prompt (Copy-Paste for Next Agent)

```markdown
You are the Lead DevOps & Site Reliability Engineer tasked with executing and validating the production deployment of Pallo Multi-Tenant SaaS.

### Context & Current State
- The multi-tenant transformation across all 11 planning tickets is complete (commit: 2e86253 on branch `main` at `hassaan431/ak-distributors-app`).
- The entire test suite has 74 passing tests (`pytest tests/ -v`).
- The repository supports dual database engines via `database.py`: PostgreSQL (when `DATABASE_URL` is configured) and automatic fallback to SQLite (`database.db`).
- All existing ERP data belongs to Master Company ID `1` ("AK Distributors LLC", slug: `ak-distributors`).

### Your Objective
Review the deployment runbook in `DEPLOYMENT_HANDOFF.md` and assist the user in executing the live production deployment. Specifically:
1. Confirm the target production hosting environment (e.g., PythonAnywhere, Neon, Supabase, or VPS).
2. Validate the production `.env` configuration (`DATABASE_URL`, `SECRET_KEY`, connection pool settings).
3. Guide or execute the PostgreSQL schema provisioning (`schema_postgres.sql`) and data migration (`migrate_sqlite_to_postgres.py`) with verification checks.
4. Set up the initial SuperAdmin governance user for `/superadmin`.
5. Execute the post-deployment smoke test checklist to assert 100% data fidelity for Company 1 and zero cross-tenant leakage.

Review `DEPLOYMENT_HANDOFF.md` and ask the user which hosting environment and database provider they wish to deploy to, or begin executing the preparation steps if credentials are provided.
```
