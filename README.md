# STRATEGOS

Initial scaffold for the STRATEGOS deterministic transformation modeling platform.

Files added:
- `STRATEGOS_MASTER_PROMPT.md` — Master Build Prompt / guiding principles (source of truth).
- `backend/` — FastAPI backend scaffold (minimal health endpoint + response formatting).
- `frontend/` — Next.js frontend scaffold (placeholder page).

Architecture diagrams:
- `docs/STRATEGOS_ARCHITECTURE_AND_INTERACTION.md` — System architecture + interaction sequence diagrams (Mermaid).


Development

Run the full local stack (Postgres + Redis + backend) with Docker if you prefer:

```powershell
docker-compose up --build
```

Or run without Docker (recommended if Docker is unavailable): use the hosted Supabase DB and a managed Redis (Upstash or similar), then run backend and frontend directly.

Backend local (PowerShell, from `backend`):

```powershell
cd backend
python -m venv .venv
. .venv\Scripts\Activate.ps1
pip install --upgrade pip
pip install -r requirements.txt
# create or copy ..\.env with DATABASE_URL and other secrets (see backend/.env.example)
.
# Run migrations and start the backend (runs alembic then uvicorn)
.\scripts\run_local.ps1
```

To start the frontend in a new terminal from the helper:

```powershell
# from backend folder
.\scripts\run_local.ps1 -StartFrontend
```

Frontend local (separate terminal in `frontend`):

```powershell
cd frontend
npm install
npm run dev
```

Notes:
- The `run_local` script (`backend/scripts/run_local.ps1`) will load `..\.env` (if present), try to activate `..\.venv`, run Alembic migrations, and start the backend on http://localhost:8000.
- For Redis use a managed provider and set the connection URL in your `.env` instead of running Redis locally.
- The `docker-compose.yml` is still in the repo if you want to use Docker later.

Next steps:
- Implement additional API domains and deterministic engine core.
- Add CI/CD and production deployment steps.
- Before building the production website and integrating AI, confirm which model you want to use.

