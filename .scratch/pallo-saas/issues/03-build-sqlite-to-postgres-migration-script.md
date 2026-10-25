# Build and Run SQLite to PostgreSQL Migration Script

Type: task
Status: open
Blocked by: 02

## Question

How do we build and execute a robust, zero-loss extraction and verification script (`migrate_sqlite_to_postgres.py`) that reads all rows from `database.db`, writes them into PostgreSQL under `company_id = 1` ("AK Distributors LLC"), resets PostgreSQL sequence counters (`setval`), and verifies 100% row-count parity across every table?
