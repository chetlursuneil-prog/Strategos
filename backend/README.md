# STRATEGOS Backend

FastAPI backend for deterministic transformation diagnostics, auth, advisory orchestration, and report generation.

## Main modules

- API composition: `app/main.py`
- Deterministic engine: `app/services/engine.py`
- Intake endpoint: `app/api/v1/intake.py`
- Advisory endpoints: `app/api/v1/advisory.py`
- Auth endpoints: `app/api/v1/auth.py`
- Reports (PDF/CSV): `app/api/v1/reports.py`
- DB models: `app/db/models.py`
- DB session/engine setup: `app/db/session.py`

## Database

- Local default: SQLite (`strategos_dev.db`)
- Production: PostgreSQL/Supabase via asyncpg
- Migrations: Alembic in `alembic/versions/`

## Required env (typical)

```bash
DATABASE_URL=postgresql://<user>:<password>@<host>:<port>/postgres
STRATEGOS_AUTH_SECRET=<strong-secret>
STRATEGOS_PUBLIC_BASE_URL=https://<your-domain>
```

Optional OpenClaw-related env:

```bash
OPENCLAW_EXECUTION_MODE=remote_http
OPENCLAW_API_BASE_URL=http://<openclaw-host>:8000
OPENCLAW_API_AGENT_PATH=/v1/agent
OPENCLAW_ALLOW_DETERMINISTIC_FALLBACK=true
```

## Local setup

```powershell
cd backend
python -m venv .venv
. .venv\Scripts\Activate.ps1
pip install --upgrade pip
pip install -r requirements.txt
python -m alembic -c alembic.ini upgrade head
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

## Seed deterministic baseline

```powershell
cd backend
python .\scripts\seed_deterministic_baseline.py
python .\scripts\smoke_seeded_engine.py
```

## Tests

```powershell
cd backend
pytest -q
```

## EC2 and OpenClaw scripts

- Strategos backend deploy: `scripts/deploy_strategos_ec2.ps1`
- OpenClaw skill deploy: `scripts/deploy_openclaw_strategos_skill.ps1`
- OpenClaw agent deploy: `scripts/deploy_openclaw_strategos_agents.ps1`
- Mode switch (integrated vs strategos-only):
  - `scripts/switch_strategos_mode.ps1`
  - `scripts/strategos_mode_switch.sh`
- OpenClaw dashboard tunnel helper: `scripts/openclaw_dashboard_tunnel.ps1`

For complete architecture and flow, see root `README.md`.
