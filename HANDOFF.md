# Handoff: Pallo SaaS Conversion (PostgreSQL Multi-Tenant Architecture)

## Executive Summary
This project converts an existing single-business wholesale ERP ("AK Distributors LLC") into **Pallo**, a multi-tenant SaaS application running on a single shared **PostgreSQL** database. 

All planning, architectural decisions, and requirement stress-testing have been **completed and approved** via `/grill-with-docs`. The execution route is charted as a shared map of 11 decision/task tickets under `.scratch/pallo-saas/` via `/wayfinder`.

No application code changes have been made yet. The codebase is clean, and the next session can immediately claim and execute the first ticket on the frontier.

---

## Destination
A production-ready **Pallo** multi-tenant SaaS running on PostgreSQL, where multiple independent businesses can self-register, manage multi-warehouse inventory, execute sales/POS, and generate custom-branded PDF invoices, with AK Distributors preserved as Company 1 with 100% data fidelity and zero cross-tenant leakage.

---

## Standing Context & Established Rules
1. **Database Engine**: Centralized PostgreSQL with `ThreadedConnectionPool` using `DATABASE_URL` (supports local Postgres and free serverless cloud Postgres like Neon/Supabase).
2. **Multi-Tenancy**: Single shared database partitioned by `company_id`. All queries strictly scoped (`WHERE company_id = ?`).
3. **Preserve AK Distributors**: Existing `database.db` SQLite data is to be migrated into PostgreSQL under `company_id = 1` ("AK Distributors LLC") with zero downtime/data loss.
4. **Branding & UI**: Keep the software's existing emerald (`#10b981`) and slate design system tokens. Do not alter color tokens. Global app brand is **Pallo**.
5. **Deployment & Restart Rules** (from `.agents/AGENTS.md`):
   - Test locally first: Run `python3 launch.py` in background.
   - Restart rule: Automatically restart server when making backend/template changes using:
     `lsof -t -i :5000 | xargs kill -9 && python3 launch.py`
   - Push to GitHub only after user explicitly verifies and approves.

---

## Canonical Documentation & Artifacts
- **Wayfinder Map**: [.scratch/pallo-saas/map.md](file:///Users/hassaanjazz/Desktop/Projects/SaaS/Pallo/.scratch/pallo-saas/map.md)
- **Implementation Plan**: [pallo_saas_single_db_plan.md](file:///Users/hassaanjazz/.gemini/antigravity-ide/brain/07de88ae-4a5a-42ca-abf8-a089338194b7/pallo_saas_single_db_plan.md)
- **ADRs**:
  - [ADR 0001: Shared Database Multi-Tenancy Architecture](file:///Users/hassaanjazz/Desktop/Projects/SaaS/Pallo/docs/adr/0001-shared-db-multi-tenancy-and-flask-evolution.md)
  - [ADR 0002: Global User Identity & Unified Authentication](file:///Users/hassaanjazz/Desktop/Projects/SaaS/Pallo/docs/adr/0002-global-user-identity-and-unified-auth.md)
  - [ADR 0003: Role-Based Financial & Cost Protection](file:///Users/hassaanjazz/Desktop/Projects/SaaS/Pallo/docs/adr/0003-role-based-financial-and-cost-protection.md)
  - [ADR 0004: Tenant Lifecycle & Soft-Deactivation Policy](file:///Users/hassaanjazz/Desktop/Projects/SaaS/Pallo/docs/adr/0004-tenant-lifecycle-and-soft-deactivation.md)
  - [ADR 0005: Database Engine Transition to PostgreSQL](file:///Users/hassaanjazz/Desktop/Projects/SaaS/Pallo/docs/adr/0005-database-engine-transition-to-postgresql.md)
- **Domain Glossary**: [GLOSSARY.md](file:///Users/hassaanjazz/Desktop/Projects/SaaS/Pallo/GLOSSARY.md)
- **Milestone Tracker**: [docs/agents/issue-tracker.md](file:///Users/hassaanjazz/Desktop/Projects/SaaS/Pallo/docs/agents/issue-tracker.md)

---

## Wayfinder Issue Map & Next Immediate Task

### Active Frontier Ticket (Take this first)
- 🟢 **[01-provision-postgres-connection-and-pooling.md](file:///Users/hassaanjazz/Desktop/Projects/SaaS/Pallo/.scratch/pallo-saas/issues/01-provision-postgres-connection-and-pooling.md)**
  - *Status*: Open, Unclaimed.
  - *Goal*: Add `psycopg2-binary` and `python-dotenv` to `requirements.txt`. Set up thread-safe `ThreadedConnectionPool` in `database.py` driven by `DATABASE_URL`.

### Blocked Dependency Chain
- **02-define-postgres-multi-tenant-schema.md** (Blocked by 01)
- **03-build-sqlite-to-postgres-migration-script.md** (Blocked by 02)
- **04-unified-auth-session-scoping-and-context.md** (Blocked by 03)
- **05-self-serve-company-registration.md** (Blocked by 04)
- **06-scope-products-inventory-and-cost-masking.md** (Blocked by 04)
- **07-scope-customers-and-sales-pos.md** (Blocked by 06)
- **08-scope-warehouses-transfers-purchases-expenses.md** (Blocked by 07)
- **09-dynamic-pdf-invoicing-and-company-branding.md** (Blocked by 07)
- **10-superadmin-platform-governance.md** (Blocked by 04)
- **11-tenant-isolation-automated-test-suite.md** (Blocked by 08, 09, 10)

---

## Suggested Skills for the Next Agent
- `wayfinder`: To work through `.scratch/pallo-saas/map.md` ticket by ticket (claim, execute, resolve).
- `security-and-hardening`: For PostgreSQL parameterized query security and tenant isolation verification.
- `test-driven-development`: For writing migration checksum checks and automated cross-tenant isolation assertions.
- `domain-modeling`: To update `GLOSSARY.md` and ADRs if new domain concepts emerge.

---

## Prompt to Start Next Session
Copy and paste this into the new window:
```text
/wayfinder We are converting the ERP to Pallo Multi-Tenant SaaS on PostgreSQL. Review the handoff document at HANDOFF.md and .scratch/pallo-saas/map.md. Claim and start working on Ticket 01 (.scratch/pallo-saas/issues/01-provision-postgres-connection-and-pooling.md).
```
