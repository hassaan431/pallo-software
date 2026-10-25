# Define PostgreSQL Multi-Tenant Schema and DDL

Type: task
Status: open
Blocked by: 01

## Question

How do we define the PostgreSQL multi-tenant schema in [database.py](file:///Users/hassaanjazz/Desktop/Projects/SaaS/Pallo/database.py) including the `companies` table, `company_id` foreign keys across all 18 entity tables, exact `NUMERIC(14, 4)` columns for financial accuracy, and composite indices on `(company_id, ...)` for sub-millisecond query filtering?
