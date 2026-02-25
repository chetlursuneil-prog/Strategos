# OpenClaw Integration Bundle (STRATEGOS)

This folder contains a deploy-ready integration bundle for wiring STRATEGOS skills into your existing OpenClaw instance on EC2.

## Contents

- `skills/strategos_skills.json`
  - API skill contract manifest for STRATEGOS REST endpoints under `/api/v1/advisory/skills/*`
- `workspace_skills/strategos-core/SKILL.md`
  - OpenClaw runtime skill folder for STRATEGOS, scoped under a dedicated namespace
- `workspace_skills/app-template-core/*`
  - Reusable scaffold for future app-specific namespaces (copy + rename per app)
- `workspace_skills/README.md`
  - Namespacing guide to keep STRATEGOS isolated from future app skills
- `agents/strategos_advisory_board.json`
  - Advisory board topology draft (6 agents) mapped to skill IDs
- `agents/strategos_advisory_agents.runtime.json`
  - Runtime-ready OpenClaw agent definitions (`strategos-*`) with skills scoping
- `.env.openclaw.example`
  - Required OpenClaw-side env vars for STRATEGOS base URL/auth
- `../scripts/validate_openclaw_bundle.py`
  - Local validation script for JSON shape/reference integrity
- `../scripts/deploy_openclaw_strategos_skill.ps1`
  - Upload/replace only STRATEGOS skill namespace on EC2
- `../scripts/remove_openclaw_strategos_skill.ps1`
  - Remove only STRATEGOS skill namespace from EC2
- `../scripts/deploy_openclaw_strategos_agents.ps1`
  - Deploy/merge only STRATEGOS advisory agents into OpenClaw (`agents.list`)
- `../scripts/remove_openclaw_strategos_agents.ps1`
  - Remove only `strategos-*` advisory agents and their workspaces

## Validate locally

```powershell
cd backend
python .\scripts\validate_openclaw_bundle.py
```

Expected output:

```text
OpenClaw bundle validation: OK
Skills: 8
Agents: 6
```

## Mapping guide for your EC2 OpenClaw

1. Keep STRATEGOS in its own namespace folder:
  - `~/.openclaw/workspace/skills/strategos-core/`
2. Deploy only STRATEGOS namespace files using:
  - `backend/scripts/deploy_openclaw_strategos_skill.ps1`
3. Keep your REST contract reference in:
  - `backend/openclaw/skills/strategos_skills.json`
4. Add env vars from `.env.openclaw.example` to OpenClaw runtime environment.
5. Ensure STRATEGOS API is reachable from EC2 and token auth is accepted.
6. Ensure advisory workflow uses the strict sequence: `create_session` -> `run_engine` -> `fetch_state` -> `fetch_contributions` -> `fetch_restructuring` -> `fetch_board_insights` before final synthesis.

## One-command EC2 Sara smoke test

Run from repo root:

```powershell
cd backend
.\scripts\smoke_openclaw_sara_e2e.ps1 -RemoteHost <EC2_PUBLIC_DNS_OR_IP> -KeyPath <PATH_TO_PEM>
```

Optional overrides:

- `-TenantId <uuid>`
- `-ModelVersionId <uuid>`
- `-ScenarioText "..."`
- `-AgentId strategos-synthesis-advisor`

Pass criteria:

- `SMOKE_OK: all strategos agents are registered`
- `SMOKE_OK: strict synthesis payload detected`
- `SMOKE_PASS: Sara/OpenClaw STRATEGOS flow is ready for live testing`

If all three lines appear, you can test immediately with Sara in Telegram.

## Isolation policy (important)

- Do not place non-STRATEGOS skills under `strategos-core`.
- Future applications must get separate namespaces (for example `finops-core`, `supplychain-core`).
- Deployment/removal scripts in `backend/scripts/` intentionally touch only `strategos-core`.
- Advisory agent scripts intentionally touch only `strategos-*` agent IDs.

This ensures skills remain separated and prevents accidental cross-app mixing as you add more applications later.

## Placeholder assumptions you should confirm on your EC2 OpenClaw

- Skill registration format (file path + loader) for your OpenClaw version.
- Auth strategy (Bearer/API key/JWT) and header naming conventions.
- Retry/backoff policy and timeout semantics.
- Whether OpenClaw expects strict response schemas per skill.

When you share those specifics, this bundle can be mapped 1:1 into your live OpenClaw configuration with exact field names.
