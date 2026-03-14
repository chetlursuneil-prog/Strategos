param(
    [Parameter(Mandatory = $true)]
    [string]$RemoteHost,

    [Parameter(Mandatory = $true)]
    [string]$KeyPath,

    [string]$User = "ubuntu"
)

$ErrorActionPreference = "Stop"

$repoRoot = Split-Path -Parent $PSScriptRoot
$localRuntimeFile = Join-Path $repoRoot "openclaw\agents\strategos_advisory_agents.runtime.json"

if (-not (Test-Path $localRuntimeFile)) {
    throw "Runtime agent file not found: $localRuntimeFile"
}

$remoteRuntimeFile = "/tmp/strategos_advisory_agents.runtime.json"
$remoteScript = @'
set -euo pipefail
CFG="/home/ubuntu/.openclaw/openclaw.json"
RUNTIME="/tmp/strategos_advisory_agents.runtime.json"
BACKUP="/home/ubuntu/.openclaw/openclaw.json.bak.strategos.$(date +%Y%m%d%H%M%S)"
cp "$CFG" "$BACKUP"
python3 - <<"PY"
import json
from pathlib import Path
cfg_path = Path('/home/ubuntu/.openclaw/openclaw.json')
runtime_path = Path('/tmp/strategos_advisory_agents.runtime.json')
cfg = json.loads(cfg_path.read_text())
runtime = json.loads(runtime_path.read_text())
strategos_entries = runtime.get('agents', [])
if 'agents' not in cfg or not isinstance(cfg['agents'], dict):
    cfg['agents'] = {}
if 'list' not in cfg['agents'] or not isinstance(cfg['agents']['list'], list):
    cfg['agents']['list'] = [{
        'id': 'main',
        'default': True,
        'workspace': cfg['agents'].get('defaults', {}).get('workspace', '/home/ubuntu/.openclaw/workspace')
    }]
existing = [a for a in cfg['agents']['list'] if isinstance(a, dict)]
existing = [a for a in existing if not str(a.get('id','')).startswith('strategos-')]
for a in existing:
    if str(a.get('id', '')).strip() == 'main':
        skills = a.get('skills')
        if not isinstance(skills, list):
            skills = []
        if 'strategos-core' not in skills:
            skills.append('strategos-core')
        a['skills'] = skills
for item in strategos_entries:
    existing.append({
        'id': item['id'],
        'name': item.get('name'),
        'workspace': item.get('workspace'),
        'model': item.get('model'),
        'skills': item.get('skills', ['strategos-core']),
        'default': False
    })
cfg['agents']['list'] = existing
cfg_path.write_text(json.dumps(cfg, indent=2) + '\n')
for item in strategos_entries:
    ws = Path(item['workspace'])
    ws.mkdir(parents=True, exist_ok=True)
    (ws / 'AGENTS.md').write_text(
        '# ' + item.get('name','STRATEGOS Agent') + '\n\n' +
        item.get('role_prompt','') + '\n\n' +
        'Execution contract (strict):\n' +
        '- You are a specialist advisor step in STRATEGOS cumulative chain orchestration.\n' +
        '- Consume only the payload provided by the orchestrator (fixed context + handoff inputs).\n' +
        '- Do not execute pseudo-commands in shell.\n' +
        '- Do not execute openclaw CLI commands from inside agent task flow.\n' +
        '- Do not call external systems beyond STRATEGOS/OpenClaw routing contract.\n' +
        '- Return strict JSON only, matching the requested output contract fields.\n'
    )
    (ws / 'TOOLS.md').write_text(
        'This workspace is used as a specialist advisory step for Strategos chain orchestration.\n' +
        'Never run openclaw CLI inside agent flow.\n' +
        'Do not run shell pseudo-commands.\n' +
        'Return strict JSON only according to orchestrator contract.\n'
    )

# Telegram commonly routes to the "main" agent. Force main workspace into the
# same deterministic STRATEGOS contract so bot replies stay consistent.
main_ws = Path('/home/ubuntu/.openclaw/workspace')
main_ws.mkdir(parents=True, exist_ok=True)
(main_ws / 'AGENTS.md').write_text(
    '# OpenClaw Main Agent (Project Router)\n\n' +
    'You are the default Telegram-facing router for multiple projects.\n' +
    'Current onboarded project: strategos.\n\n' +
    'Routing contract:\n' +
    '- If user requests STRATEGOS analysis (or no project is specified), run STRATEGOS deterministic flow.\n' +
    '- If user references another project/app that is not onboarded yet, ask for project onboarding details (base URL, token env var, skill namespace, deterministic flow script path).\n' +
    '- Never claim a project is connected unless deterministic connectivity is confirmed.\n\n' +
    'Execution contract (for strategos):\n' +
    '- Do not narrate progress. Do not output placeholders.\n' +
    '- Do not output acknowledgement text like accepted/in progress/announcement.\n' +
    '- Do not execute pseudo-commands like strategos.run_engine in shell.\n' +
    '- Do not run openclaw CLI commands inside the task flow.\n' +
    '- Use exec tool with this exact command:\n' +
    '  python3 /home/ubuntu/.openclaw/workspace/skills/strategos-core/strategos_telegram_flow.py --scenario "<user text>" --base-url "${STRATEGOS_API_BASE_URL}" --token "${STRATEGOS_API_TOKEN}"\n' +
    '- Return only one compact JSON object with keys: session_id, deterministic_state, contributions, restructuring, board_insights, executive_summary.\n'
)
(main_ws / 'TOOLS.md').write_text(
    'Use only STRATEGOS REST workflow via strategos-core skill.\n' +
    'Never run openclaw CLI inside agent flow.\n' +
    'Use exec + python3 script at /home/ubuntu/.openclaw/workspace/skills/strategos-core/strategos_telegram_flow.py.\n' +
    'No direct DB access.\n'
)
print('Applied strategos agents:', len(strategos_entries))
PY
/home/ubuntu/.npm-global/bin/openclaw agents list --json

# Reset per-agent sessions so stale conversational state cannot survive redeploy.
for id in \
  strategos-schema-extraction \
  strategos-strategy-advisor \
  strategos-risk-officer \
  strategos-architecture-advisor \
  strategos-financial-impact-advisor \
  strategos-synthesis-advisor \
  main; do
  sdir="/home/ubuntu/.openclaw/agents/$id/sessions"
  mkdir -p "$sdir"
  printf '[]\n' > "$sdir/sessions.json"
done
'@
$remoteScriptB64 = [Convert]::ToBase64String([Text.Encoding]::UTF8.GetBytes($remoteScript))

Write-Host "[1/3] Uploading STRATEGOS advisory runtime config..."
scp -o StrictHostKeyChecking=no -i $KeyPath $localRuntimeFile "${User}@${RemoteHost}:${remoteRuntimeFile}"

Write-Host "[2/3] Applying namespaced STRATEGOS agents on EC2..."
ssh -o StrictHostKeyChecking=no -i $KeyPath "${User}@${RemoteHost}" "echo '$remoteScriptB64' | base64 -d | tr -d '\r' | bash"

Write-Host "[3/3] Running quick role validation prompts..."
$validate = @'
set -euo pipefail
for id in strategos-schema-extraction strategos-strategy-advisor strategos-risk-officer strategos-architecture-advisor strategos-financial-impact-advisor strategos-synthesis-advisor; do
  echo "=== $id ==="
    /home/ubuntu/.npm-global/bin/openclaw agent --agent "$id" --message "In one sentence, state your role and confirm you only use STRATEGOS REST skills." --json | sed -n '1,20p'
  echo
done
'@
$validateB64 = [Convert]::ToBase64String([Text.Encoding]::UTF8.GetBytes($validate))
ssh -o StrictHostKeyChecking=no -i $KeyPath "${User}@${RemoteHost}" "echo '$validateB64' | base64 -d | tr -d '\r' | bash"

Write-Host "Done. STRATEGOS advisory agents deployed in isolated strategos-* namespace."
