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
    [string]$ScenarioText = "Sara smoke test. Telecom transformation baseline. Revenue: 1000M. Operating costs: 620M. Margin: 11%. Technical debt: 68%."
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

PROMPT="Run STRATEGOS strict advisory flow for this scenario: $SCENARIO_TEXT\n\nUse tenant_id=$TENANT_ID and model_version_id=$MODEL_VERSION_ID.\nMandatory sequence: create_session -> run_engine -> fetch_state -> fetch_contributions -> fetch_restructuring -> fetch_board_insights.\nReturn one compact JSON object with keys exactly: session_id, deterministic_state, contributions, restructuring, board_insights, executive_summary."

$OPENCLAW_BIN agent --agent "$AGENT_ID" --message "$PROMPT" --json > /tmp/strategos_sara_smoke_response.json

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
    text_blob = json.dumps(obj)

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
'@

$remoteScriptB64 = [Convert]::ToBase64String([Text.Encoding]::UTF8.GetBytes($remoteScript))
$openclawBinLiteral = Convert-ToShellLiteral -Value $OpenClawBin
$agentIdLiteral = Convert-ToShellLiteral -Value $AgentId
$tenantIdLiteral = Convert-ToShellLiteral -Value $TenantId
$modelVersionIdLiteral = Convert-ToShellLiteral -Value $ModelVersionId
$scenarioTextLiteral = Convert-ToShellLiteral -Value $ScenarioText

$remoteCommand = "export OPENCLAW_BIN=$openclawBinLiteral AGENT_ID=$agentIdLiteral TENANT_ID=$tenantIdLiteral MODEL_VERSION_ID=$modelVersionIdLiteral SCENARIO_TEXT=$scenarioTextLiteral; echo '$remoteScriptB64' | base64 -d | tr -d '\r' | bash"
ssh -o StrictHostKeyChecking=no -i $KeyPath "${User}@${RemoteHost}" $remoteCommand
