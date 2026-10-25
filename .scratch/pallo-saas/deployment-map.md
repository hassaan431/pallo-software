# Wayfinder Map: Pallo SaaS Production Deployment & Cutover

## Destination

A live, production-deployed Pallo Multi-Tenant SaaS accessible on a secure public HTTPS URL (Render.com), connected to high-availability serverless PostgreSQL (Neon.tech), with 100% of AK Distributors LLC data migrated into Company 1, platform SuperAdmin governance active, and zero cross-tenant leakage.

## Notes

- **Domain**: Cloud Infrastructure, Site Reliability Engineering, Production Cutover, Zero-Data-Loss Migration.
- **Hosting Stack**: Render Free Web Service (Compute) + Neon Serverless PostgreSQL 16 (Database) + Cloudflare R2 / Local Fallback (Storage).
- **Target Persona**: Guided step-by-step for a beginner with zero prior DevOps experience; absolute safety and zero data loss.
- **Issue Tracker**: Local Markdown tracker under `.scratch/pallo-saas/deployment-issues/`.

## Decisions & Tickets

| Ticket | Name | Type | Status | Summary |
| :--- | :--- | :--- | :--- | :--- |
| **D1** | [Provision Neon PostgreSQL Database](deployment-issues/d1-provision-neon-postgres.md) | `wayfinder:task` (HITL) | 🟢 **DONE** | Neon database provisioned and connected via connection string. |
| **D2** | [Validate Schema & Dry-Run Migration](deployment-issues/d2-verify-schema-and-dry-run.md) | `wayfinder:task` (AFK) | 🟢 **DONE** | PostgreSQL schema applied; composite keys, indices, and constraints verified. |
| **D3** | [Execute Live Migration & SuperAdmin](deployment-issues/d3-execute-live-migration-and-superadmin.md) | `wayfinder:task` (AFK) | 🟢 **DONE** | 991 records migrated with 100% fidelity; SuperAdmin provisioned. |
| **D4** | [Push Production Code to GitHub](deployment-issues/d4-push-production-code-to-github.md) | `wayfinder:task` (HITL) | 🟢 **DONE** | Code committed and pushed to `pallo-software` (`main` and `master`). |
| **D5** | [Launch Web Service on Render](deployment-issues/d5-launch-render-web-service.md) | `wayfinder:task` (HITL) | 🟢 **DONE** | Live Render web service active at `https://pallo-app.onrender.com`. |
| **D6** | [Production Smoke Test & Verification](deployment-issues/d6-production-smoke-test-verification.md) | `wayfinder:task` (HITL) | 🟢 **DONE** | Full production smoke test verified: 200 OK across all ERP workstations and SuperAdmin. |

## Not yet specified

- **Cloudflare R2 API Token Provisioning**: Once live, create the Cloudflare R2 bucket to permanently store newly uploaded company logos outside ephemeral container disk.
- **Custom Domain & DNS Setup**: Mapping a branded domain (e.g., `app.pallo.com`) to the Render web service.

## Out of scope

- **Paid Compute Tiers**: Staying strictly on Render and Neon free tiers for initial launch ($0/month).
- **Stripe Billing Integration**: Deferred until user is ready to monetize external signups.
