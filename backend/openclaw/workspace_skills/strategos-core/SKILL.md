---
name: strategos-core
description: STRATEGOS deterministic advisory operations. Use for session creation, engine execution, state retrieval, contribution analysis, restructuring suggestions, and model/rule inspection through STRATEGOS REST endpoints.
---

# STRATEGOS Core Skill

Use this skill only for STRATEGOS advisory workflows.

IMPORTANT:
- `strategos.*` labels are logical workflow step names, not executable shell commands.
- Never run `openclaw ...` inside agent execution for STRATEGOS flow.
- Execute the packaged Python flow script using the `exec` tool, then return strict JSON.

## Endpoints (base: STRATEGOS_API_BASE_URL)

- `POST /advisory/skills/create_session`
- `POST /advisory/skills/run_engine`
- `GET /advisory/skills/state/{session_id}`
- `GET /advisory/skills/contributions/{session_id}`
- `GET /advisory/skills/restructuring/{session_id}`
- `GET /advisory/skills/board_insights/{session_id}`
- `GET /advisory/skills/model_versions`
- `GET /advisory/skills/show_rules`
- `POST /intake`

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

## Deterministic execution path (required)

Use this exact command pattern via `exec`:

```bash
python3 /home/ubuntu/.openclaw/workspace/skills/strategos-core/strategos_telegram_flow.py \
  --scenario "<raw user scenario text>" \
  --base-url "${STRATEGOS_API_BASE_URL}" \
  --token "${STRATEGOS_API_TOKEN}"
```

Optional flags:
- `--tenant-id <uuid>`
- `--model-version-id <uuid>`

The script returns one JSON object with keys:
- `session_id`
- `deterministic_state`
- `contributions`
- `restructuring`
- `board_insights`
- `executive_summary`

If script execution fails, report the exact error and do not invent deterministic values.

## Mandatory contract for Sara/OpenClaw orchestration

- Do not return a final advisory response unless `session_id` is present.
- Do not skip any step in the session-first flow.
- Do not output acknowledgement-only text such as "accepted", "in progress", or "announcement".
- Final board-ready payload must include:
- `session_id`
- `deterministic_state`
- `contributions`
- `restructuring`
- `board_insights`
- `executive_summary`
