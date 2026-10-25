# Ticket D1: Provision Neon PostgreSQL Database

**Labels**: `wayfinder:task`
**Type**: HITL (Human In The Loop)
**Status**: In Progress

## Question / Objective
Create a free PostgreSQL database on Neon.tech and obtain the secret `DATABASE_URL` connection string so the migration engine can connect.

## Step-by-Step Instructions for the User
1. Open your browser and go to: [https://neon.tech](https://neon.tech)
2. Sign up for a free account (using Google or GitHub).
3. Click **"Create Project"**:
   - Name: `pallo-db`
   - Postgres Version: 16 (default)
   - Region: Any (e.g. US East or EU Central)
4. Copy the connection string under **"Connect to your database"**:
   - It will look like: `postgresql://neondb_owner:***@ep-xyz.us-east-2.aws.neon.tech/neondb?sslmode=require`
5. Paste it into the assistant chat.
