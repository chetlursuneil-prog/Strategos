---
name: strategos-core
description: STRATEGOS deterministic advisory operations. Use for session creation, engine execution, state retrieval, contribution analysis, restructuring suggestions, and model/rule inspection through STRATEGOS REST endpoints.
---

# STRATEGOS Core Skill

Use this skill only for STRATEGOS advisory workflows.

## Endpoints (base: STRATEGOS_API_BASE_URL)

- `POST /advisory/skills/create_session`
- `POST /advisory/skills/run_engine`
- `GET /advisory/skills/state/{session_id}`
- `GET /advisory/skills/contributions/{session_id}`
- `GET /advisory/skills/restructuring/{session_id}`
- `GET /advisory/skills/board_insights/{session_id}`
- `GET /advisory/skills/model_versions`
- `GET /advisory/skills/show_rules`

## Auth

Use bearer token auth with:

- Header: `Authorization`
- Value: `Bearer ${STRATEGOS_API_TOKEN}`

## Operational constraints

- Keep requests deterministic and auditable.
- Prefer explicit `tenant_id`, `model_version_id`, and `session_id` where available.
- Do not call non-STRATEGOS domains from this skill.
- Keep all STRATEGOS-specific logic in this namespace only.

## Session-first flow

1. Create session (`create_session`)
2. Run engine (`run_engine`)
3. Fetch deterministic outputs (`state`, `contributions`, `restructuring`)
4. Fetch board synthesis inputs (`board_insights`)
5. Inspect model/rules as needed (`model_versions`, `show_rules`)

## Mandatory contract for Sara/OpenClaw orchestration

- Do not return a final advisory response unless `session_id` is present.
- Do not skip any step in the session-first flow.
- Final board-ready payload must include:
	- `session_id`
	- `deterministic_state`
	- `contributions`
	- `restructuring`
	- `board_insights`
	- `executive_summary`
