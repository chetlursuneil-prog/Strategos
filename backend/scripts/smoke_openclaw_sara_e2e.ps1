param(
    [Parameter(Mandatory = $true)]
    [string]$RemoteHost,

    [Parameter(Mandatory = $true)]
    [string]$KeyPath,

    [string]$User = "ubuntu",
    [string]$OpenClawBin = "/home/ubuntu/.npm-global/bin/openclaw",
    [string]$AgentId = "strategos-synthesis-advisor",
    [string]$TenantId = "c6ff3608-37ba-41da-a6ba-f8ff12c0c2e3",
    [string]$ModelVersionId = "8a547931-4a5f-4948-81f4-66b169c210e7",
    [string]$ScenarioText = "Sara smoke test. Telecom transformation baseline. Revenue: 1000M. Operating costs: 620M. Margin: 11%. Technical debt: 68%.",
    [string]$StrategosApiBaseUrl = "http://172.31.37.155:8000/api/v1",
    [string]$StrategosApiToken = "ff7ddb092fd74c81448eda0e250a673b2065922e420eca232046e5e78fde3464"
)

$ErrorActionPreference = "Stop"

function Convert-ToShellLiteral {
        param([Parameter(Mandatory = $true)][string]$Value)
    $escapedSingleQuoteToken = "'`"'`"'"
    $segments = $Value -split "'"
    return "'" + ($segments -join $escapedSingleQuoteToken) + "'"
}

$remoteScript = @'
set -euo pipefail

if [ ! -x "$OPENCLAW_BIN" ]; then
    echo "SMOKE_FAIL: openclaw binary not found or not executable at $OPENCLAW_BIN"
  exit 1
fi

# Ensure user-level gateway service has STRATEGOS connectivity env vars.
SVC="/home/ubuntu/.config/systemd/user/openclaw-gateway.service"
if [ -f "$SVC" ]; then
  grep -q '^Environment=STRATEGOS_API_BASE_URL=' "$SVC" \
    && sed -i "s|^Environment=STRATEGOS_API_BASE_URL=.*|Environment=STRATEGOS_API_BASE_URL=$STRATEGOS_API_BASE_URL|" "$SVC" \
    || printf '\nEnvironment=STRATEGOS_API_BASE_URL=%s\n' "$STRATEGOS_API_BASE_URL" >> "$SVC"

  grep -q '^Environment=STRATEGOS_API_TOKEN=' "$SVC" \
    && sed -i "s|^Environment=STRATEGOS_API_TOKEN=.*|Environment=STRATEGOS_API_TOKEN=$STRATEGOS_API_TOKEN|" "$SVC" \
    || printf 'Environment=STRATEGOS_API_TOKEN=%s\n' "$STRATEGOS_API_TOKEN" >> "$SVC"

  systemctl --user daemon-reload || true
  systemctl --user restart openclaw-gateway || true
  sleep 2
fi

# Force main agent (Telegram default) into project-router behavior with
# deterministic STRATEGOS execution as the currently onboarded project.
MAIN_WS="/home/ubuntu/.openclaw/workspace"
mkdir -p "$MAIN_WS"
cat > "$MAIN_WS/AGENTS.md" <<'EOF'
# OpenClaw Main Agent (Project Router)

You are the default Telegram-facing router for multiple projects.
Current onboarded project: strategos.

Routing contract:
- If user requests STRATEGOS analysis (or no project is specified), run STRATEGOS deterministic flow.
- If user references another project/app that is not onboarded yet, ask for project onboarding details (base URL, token env var, skill namespace, deterministic flow script path).
- Never claim a project is connected unless deterministic connectivity is confirmed.

Execution contract (for strategos):
- Do not narrate progress. Do not output placeholders.
- Do not output acknowledgement text like accepted/in progress/announcement.
- Do not execute pseudo-commands like strategos.run_engine in shell.
- Do not run openclaw CLI commands inside the task flow.
- Use exec tool with this exact command:
  python3 /home/ubuntu/.openclaw/workspace/skills/strategos-core/strategos_telegram_flow.py --scenario "<user text>" --base-url "${STRATEGOS_API_BASE_URL}" --token "${STRATEGOS_API_TOKEN}"
- Return only one compact JSON object with keys: session_id, deterministic_state, contributions, restructuring, board_insights, executive_summary.
EOF

cat > "$MAIN_WS/TOOLS.md" <<'EOF'
Use only deterministic, project-scoped flows.
Current onboarded project: strategos.
For strategos, use:
python3 /home/ubuntu/.openclaw/workspace/skills/strategos-core/strategos_telegram_flow.py --scenario "<user text>" --base-url "${STRATEGOS_API_BASE_URL}" --token "${STRATEGOS_API_TOKEN}"
Never run openclaw CLI inside agent task flow.
EOF

# Reset main session memory to remove stale conversational behavior.
MAIN_SESSION_FILE="/home/ubuntu/.openclaw/agents/main/sessions/sessions.json"
mkdir -p "$(dirname "$MAIN_SESSION_FILE")"
printf '[]\n' > "$MAIN_SESSION_FILE"

$OPENCLAW_BIN agents list --json > /tmp/strategos_agents_list.json
python3 - <<'PY'
import json
from pathlib import Path

required = {
    "strategos-schema-extraction",
    "strategos-strategy-advisor",
    "strategos-risk-officer",
    "strategos-architecture-advisor",
    "strategos-financial-impact-advisor",
    "strategos-synthesis-advisor",
}

p = Path('/tmp/strategos_agents_list.json')
text = p.read_text(encoding='utf-8')
start = -1
for marker in ('{', '['):
    idx = text.find(marker)
    if idx != -1 and (start == -1 or idx < start):
        start = idx
if start > 0:
    text = text[start:]
try:
    payload = json.loads(text)
except Exception:
    print('SMOKE_FAIL: could not parse agents list JSON')
    raise SystemExit(1)

agents = payload if isinstance(payload, list) else payload.get('agents', payload.get('list', []))
ids = {str(a.get('id')) for a in agents if isinstance(a, dict)}
missing = sorted(required - ids)
if missing:
    print('SMOKE_FAIL: missing strategos agents:', ', '.join(missing))
    raise SystemExit(1)

print('SMOKE_OK: all strategos agents are registered')
PY

PROMPT="Run STRATEGOS strict advisory flow for this scenario: $SCENARIO_TEXT\n\nUse tenant_id=$TENANT_ID and model_version_id=$MODEL_VERSION_ID.\nMandatory sequence: create_session -> run_engine -> fetch_state -> fetch_contributions -> fetch_restructuring -> fetch_board_insights.\nDo not acknowledge. Do not announce progress. Do not say accepted/in progress.\nReturn one compact JSON object with keys exactly: session_id, deterministic_state, contributions, restructuring, board_insights, executive_summary."

# Reset the synthesis agent session before smoke to avoid stale behavioral drift.
SESSION_FILE="/home/ubuntu/.openclaw/agents/$AGENT_ID/sessions/sessions.json"
mkdir -p "$(dirname "$SESSION_FILE")"
printf '[]\n' > "$SESSION_FILE"

SMOKE_SESSION_ID="$(python3 - <<'PY'
import uuid
print(uuid.uuid4())
PY
)"
SMOKE_TO="+1555$(python3 - <<'PY'
import random
print(''.join(str(random.randint(0, 9)) for _ in range(7)))
PY
)"

# Use an isolated session each run to avoid stale conversational state.
$OPENCLAW_BIN agent \
  --agent "$AGENT_ID" \
  --to "$SMOKE_TO" \
  --session-id "$SMOKE_SESSION_ID" \
  --thinking off \
  --timeout 180 \
  --message "$PROMPT" \
  --json > /tmp/strategos_sara_smoke_response.json

python3 - <<'PY'
import json
import re
from pathlib import Path

required_keys = [
    'session_id',
    'deterministic_state',
    'contributions',
    'restructuring',
    'board_insights',
    'executive_summary',
]

raw = Path('/tmp/strategos_sara_smoke_response.json').read_text(encoding='utf-8', errors='ignore')

# Parse CLI JSON if possible; otherwise validate from raw content.
obj = None
try:
    obj = json.loads(raw)
except Exception:
    pass

text_blob = raw
if isinstance(obj, dict):
    # Prefer payload text if the CLI wrapped the response.
    payload_text = None
    try:
        payloads = ((obj.get('result') or {}).get('payloads') or [])
        if payloads and isinstance(payloads[0], dict):
            payload_text = payloads[0].get('text')
    except Exception:
        payload_text = None
    text_blob = payload_text if isinstance(payload_text, str) and payload_text.strip() else json.dumps(obj)

# If payload text itself is JSON, parse it for key checks.
try:
    maybe_inner = json.loads(text_blob)
    text_blob = json.dumps(maybe_inner)
except Exception:
    pass

lower_blob = text_blob.lower()
if any(marker in lower_blob for marker in ('accepted', 'in progress', 'announcement', 'process is currently underway')):
    print('SMOKE_FAIL: agent returned async acknowledgment text instead of final strict JSON')
    print('--- RAW RESPONSE (first 1200 chars) ---')
    print(raw[:1200])
    raise SystemExit(1)

missing = [k for k in required_keys if k not in text_blob]
if missing:
    print('SMOKE_FAIL: missing required synthesis keys:', ', '.join(missing))
    print('--- RAW RESPONSE (first 1200 chars) ---')
    print(raw[:1200])
    raise SystemExit(1)

uuid_match = re.search(r'[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}', text_blob)
if not uuid_match:
    print('SMOKE_FAIL: no session_id-like UUID detected in response')
    print('--- RAW RESPONSE (first 1200 chars) ---')
    print(raw[:1200])
    raise SystemExit(1)

print('SMOKE_OK: strict synthesis payload detected')
print('SESSION_ID_CANDIDATE:', uuid_match.group(0))
print('SMOKE_PASS: Sara/OpenClaw STRATEGOS flow is ready for live testing')
PY

# Verify Telegram-default route via main agent as well.
$OPENCLAW_BIN agent \
  --agent "main" \
  --to "$SMOKE_TO" \
  --session-id "$SMOKE_SESSION_ID-main" \
  --thinking off \
  --timeout 180 \
  --message "$PROMPT" \
  --json > /tmp/strategos_sara_smoke_main_response.json

python3 - <<'PY'
import json
from pathlib import Path

required_keys = [
    'session_id',
    'deterministic_state',
    'contributions',
    'restructuring',
    'board_insights',
    'executive_summary',
]

raw = Path('/tmp/strategos_sara_smoke_main_response.json').read_text(encoding='utf-8', errors='ignore')
obj = None
try:
    obj = json.loads(raw)
except Exception:
    pass

text_blob = raw
if isinstance(obj, dict):
    payload_text = None
    try:
        payloads = ((obj.get('result') or {}).get('payloads') or [])
        if payloads and isinstance(payloads[0], dict):
            payload_text = payloads[0].get('text')
    except Exception:
        payload_text = None
    text_blob = payload_text if isinstance(payload_text, str) and payload_text.strip() else json.dumps(obj)

try:
    maybe_inner = json.loads(text_blob)
    text_blob = json.dumps(maybe_inner)
except Exception:
    pass

lower_blob = text_blob.lower()
if any(marker in lower_blob for marker in ('accepted', 'in progress', 'announcement', 'process is currently underway')):
    print('SMOKE_FAIL: main agent returned async acknowledgment text instead of final strict JSON')
    print('--- RAW MAIN RESPONSE (first 1200 chars) ---')
    print(raw[:1200])
    raise SystemExit(1)

missing = [k for k in required_keys if k not in text_blob]
if missing:
    print('SMOKE_FAIL: main agent missing required synthesis keys:', ', '.join(missing))
    print('--- RAW MAIN RESPONSE (first 1200 chars) ---')
    print(raw[:1200])
    raise SystemExit(1)

print('SMOKE_OK: main agent strict payload detected')
PY
'@

$remoteScriptB64 = [Convert]::ToBase64String([Text.Encoding]::UTF8.GetBytes($remoteScript))
$openclawBinLiteral = Convert-ToShellLiteral -Value $OpenClawBin
$agentIdLiteral = Convert-ToShellLiteral -Value $AgentId
$tenantIdLiteral = Convert-ToShellLiteral -Value $TenantId
$modelVersionIdLiteral = Convert-ToShellLiteral -Value $ModelVersionId
$scenarioTextLiteral = Convert-ToShellLiteral -Value $ScenarioText
$strategosApiBaseUrlLiteral = Convert-ToShellLiteral -Value $StrategosApiBaseUrl
$strategosApiTokenLiteral = Convert-ToShellLiteral -Value $StrategosApiToken

$remoteCommand = "export OPENCLAW_BIN=$openclawBinLiteral AGENT_ID=$agentIdLiteral TENANT_ID=$tenantIdLiteral MODEL_VERSION_ID=$modelVersionIdLiteral SCENARIO_TEXT=$scenarioTextLiteral STRATEGOS_API_BASE_URL=$strategosApiBaseUrlLiteral STRATEGOS_API_TOKEN=$strategosApiTokenLiteral; echo '$remoteScriptB64' | base64 -d | tr -d '\r' | bash"
ssh -o StrictHostKeyChecking=no -i $KeyPath "${User}@${RemoteHost}" $remoteCommand
