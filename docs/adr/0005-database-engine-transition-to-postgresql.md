# Transition from SQLite to PostgreSQL for SaaS Scalability

We decided to migrate the primary database engine from SQLite to PostgreSQL for the Pallo multi-tenant SaaS. While SQLite is suitable for single-user local applications, PostgreSQL is required to support concurrent multi-company read/write traffic, eliminate database write-lock contention, provide exact financial decimal precision, and unlock native enterprise security features.

## Considered Options

- **Retaining SQLite (`database.db`)**: Zero setup and file-based simplicity, but suffers from single-writer lock bottlenecks (`database is locked` errors under concurrent user traffic), lacks connection pooling, and degrades under multi-worker web servers (Gunicorn/uWSGI).
- **PostgreSQL (Selected)**: The industry benchmark for SaaS and ERP systems. Provides Multi-Version Concurrency Control (MVCC) for non-blocking concurrent writes, exact fixed-point financial precision (`NUMERIC`), connection pooling (`ThreadedConnectionPool`), and native Row-Level Security (RLS). Free serverless hosting is accessible via Neon or Supabase.

## Consequences

- Project dependencies will include `psycopg2-binary` and `python-dotenv` for managing `DATABASE_URL`.
- [database.py](file:///Users/hassaanjazz/Desktop/Projects/SaaS/Pallo/database.py) will connect to PostgreSQL using a connection pool.
- A one-time migration utility (`migrate_sqlite_to_postgres.py`) will safely extract all existing records from `database.db` and load them into PostgreSQL under `company_id = 1` ("AK Distributors LLC").
- Query parameter placeholders will follow standard PostgreSQL parameterization (`%s` via `RealDictCursor`), with a compatibility execution helper in `database.py`.
