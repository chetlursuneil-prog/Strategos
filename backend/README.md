# STRATEGOS Backend — Local dev & migrations

This file describes how to run migrations locally against a Supabase Postgres database **without committing secrets** to the repository.

1) Create a local `.env` in `backend/` (DO NOT commit this file).

Example `.env` (replace values; keep this file out of git):

```
SUPABASE_URL=https://<your-project-ref>.supabase.co
SUPABASE_DB_URL=postgresql://<user>:<password>@db.<host>.supabase.co:5432/postgres
SUPABASE_SERVICE_ROLE_KEY=<service_role_key_here>

DATABASE_URL=${SUPABASE_DB_URL}
REDIS_URL=redis://localhost:6379/0
SECRET_KEY=replace_with_secure_key
ENV=development
OPENCLAW_BIN=/home/ubuntu/.npm-global/bin/openclaw
OPENCLAW_AGENT_TIMEOUT_SECONDS=90
```

2) Install dependencies and activate a virtual environment (PowerShell):

```powershell
cd backend
python -m venv .venv
. .venv\Scripts\Activate.ps1
pip install --upgrade pip
pip install -r requirements.txt
```

3) Export the environment variables for the current session (PowerShell):

```powershell
$env:DATABASE_URL = 'postgresql://postgres:<password>@aws-1-ap-northeast-1.pooler.supabase.com:5432/postgres'
$env:SUPABASE_SERVICE_ROLE_KEY = '<service_role_key_here>'
```

4) Create and run migrations (uses `alembic.ini` in `backend/`):

```powershell
# create an autogen revision (this reads models from app.db.base + app.db.models)
alembic -c alembic.ini revision --autogenerate -m "initial"

# apply migrations to the target database
alembic -c alembic.ini upgrade head
```

Notes & security
- Never paste the `service_role` key into public chat or commit it to git.
- For CI, add `DATABASE_URL` and `SUPABASE_SERVICE_ROLE_KEY` to GitHub Actions secrets.
- If you prefer, run migrations against a local Docker Postgres for development and only run production migrations against Supabase.

## OpenClaw integration bundle

An OpenClaw-ready skills/agents bundle is now available in `backend/openclaw/`.

```powershell
cd backend
python .\scripts\validate_openclaw_bundle.py
```

See `backend/openclaw/README.md` for EC2 integration mapping steps.

## Deterministic baseline seeding

Use these scripts to populate a usable deterministic baseline (metrics, coefficients, rules, thresholds, restructuring templates):

```powershell
cd backend

# seed baseline into the currently configured DATABASE_URL
python .\scripts\seed_deterministic_baseline.py

# optional local smoke check for seeded behavior
python .\scripts\smoke_seeded_engine.py
```

Optional target override:

- `SEED_TENANT_ID` (UUID)
- `SEED_MODEL_VERSION_ID` (UUID)

If not provided, the script uses the first tenant/model version or creates a baseline pair.
