# STRATEGOS

STRATEGOS is a deterministic transformation diagnostics platform with two user channels:

- Web app flow (Next.js) for internal workspace and admin operations.
- OpenClaw/Sara flow (Telegram/OpenClaw runtime) for advisory-agent orchestration.

## Architecture (current)

The deployed end-to-end architecture uses 14 core components grouped across 6 layers.

```mermaid
flowchart LR
	subgraph CH[Channels]
		WEB[Web User\nfrontend/app/dashboard/workspace/page.tsx]
		TG[Telegram User\n(OpenClaw/Sara channel)]
	end

	subgraph FE[Frontend]
		NEXT[Next.js App\nfrontend/app/*\nfrontend/lib/api.ts]
		ADMINUI[Admin Portal\nfrontend/app/internal/admin/page.tsx]
	end

	subgraph EDGE[Edge]
		NGINX[Nginx Reverse Proxy\n/:3000 and /api:8000]
		TLS[Let's Encrypt TLS\ncertbot + nginx plugin]
	end

	subgraph BE[Backend API (FastAPI)]
		MAIN[Router Composition\nbackend/app/main.py]
		INTAKE[/api/v1/intake\nbackend/app/api/v1/intake.py]
		ADVISORY[/api/v1/advisory/skills/*\nbackend/app/api/v1/advisory.py]
		ADMIN[/api/v1/admin/*\nbackend/app/api/v1/admin.py]
		RULES[/api/v1/rules*\nbackend/app/api/v1/rules.py]
		ENGINE[Deterministic Engine\nbackend/app/services/engine.py]
	end

	subgraph OC[OpenClaw Assets]
		OCSKILLS[Skill Contract\nbackend/openclaw/skills/strategos_skills.json]
		OCBOARD[Board Topology\nbackend/openclaw/agents/strategos_advisory_board.json]
		OCRUNTIME[Runtime Agents\nbackend/openclaw/agents/strategos_advisory_agents.runtime.json]
	end

	subgraph DATA[Data]
		DB[(Postgres)]
		MODELS[Models + Entities\nbackend/app/db/models.py]
		SEED[Deterministic Seed Rules\nbackend/scripts/seed_deterministic_baseline.py]
	end

	WEB --> NEXT --> NGINX --> MAIN
	TG --> OCRUNTIME --> ADVISORY

	ADMINUI --> ADMIN
	NEXT --> INTAKE
	NEXT --> ADVISORY

	MAIN --> INTAKE
	MAIN --> ADVISORY
	MAIN --> ADMIN
	MAIN --> RULES

	INTAKE --> ENGINE
	ADVISORY --> ENGINE
	RULES --> DB
	ADMIN --> DB
	ENGINE --> DB

	ENGINE --> MODELS
	SEED --> DB
	OCSKILLS --> ADVISORY
	OCBOARD --> ADVISORY
	OCRUNTIME --> ADVISORY
	TLS --> NGINX
```

## File map (where key logic lives)

### OpenClaw integration

- Skills contract: `backend/openclaw/skills/strategos_skills.json`
- Advisory board topology: `backend/openclaw/agents/strategos_advisory_board.json`
- Runtime agent profile: `backend/openclaw/agents/strategos_advisory_agents.runtime.json`
- OpenClaw bundle guide: `backend/openclaw/README.md`
- Bundle validator: `backend/scripts/validate_openclaw_bundle.py`
- EC2 OpenClaw smoke test: `backend/scripts/smoke_openclaw_sara_e2e.ps1`

### Deterministic engine and rules

- Engine execution: `backend/app/services/engine.py`
- Engine API endpoint: `backend/app/api/v1/engine.py`
- Intake endpoint (text to deterministic run): `backend/app/api/v1/intake.py`
- Advisory skill endpoints: `backend/app/api/v1/advisory.py`
- Rules CRUD and activation: `backend/app/api/v1/rules.py`
- NL admin command parser: `backend/app/api/v1/admin.py`
- DB entities (rules, impacts, conditions, sessions, audit): `backend/app/db/models.py`
- Baseline deterministic seed data: `backend/scripts/seed_deterministic_baseline.py`

### Frontend orchestration

- Web workspace flow: `frontend/app/dashboard/workspace/page.tsx`
- Internal admin + CRUD flow: `frontend/app/internal/admin/page.tsx`
- Shared frontend API client: `frontend/lib/api.ts`

## End-to-end flow summary

### Web app path

1. User submits business context in workspace UI.
2. Frontend calls `POST /api/v1/intake`.
3. Backend runs deterministic engine and persists session snapshot.
4. Frontend calls advisory skill endpoints for state/contributions/restructuring.
5. Frontend optionally calls board insights endpoint for multi-agent insights.

### Telegram/OpenClaw path

1. User sends STRATEGOS request to Sara in Telegram.
2. OpenClaw runtime invokes STRATEGOS advisory skills (`create_session`, `run_engine`, `fetch_*`).
3. FastAPI advisory endpoints call deterministic engine and return structured payload.
4. OpenClaw synthesis agent composes final board-style response.

## Local development

### Backend

```powershell
cd backend
python -m venv .venv
. .venv\Scripts\Activate.ps1
pip install --upgrade pip
pip install -r requirements.txt
.\scripts\run_local.ps1
```

### Frontend

```powershell
cd frontend
npm install
npm run dev
```

### Docker (optional)

```powershell
docker-compose up --build
```

## Operational checks

Backend health:

```powershell
curl -sS -i http://localhost:8000/api/v1/health
```

OpenClaw bundle validation:

```powershell
cd backend
python .\scripts\validate_openclaw_bundle.py
```

OpenClaw Sara E2E smoke test:

```powershell
cd backend
.\scripts\smoke_openclaw_sara_e2e.ps1 -RemoteHost <OPENCLAW_HOST> -KeyPath <PATH_TO_PEM>
```

## Detailed architecture docs

- `docs/STRATEGOS_ARCHITECTURE_AND_INTERACTION.md`
- `docs/architecture.mmd`
- `docs/architecture_pngsafe.mmd`

