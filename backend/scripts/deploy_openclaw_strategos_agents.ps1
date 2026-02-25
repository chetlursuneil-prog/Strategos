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
    (ws / 'AGENTS.md').write_text('# ' + item.get('name','STRATEGOS Agent') + '\n\n' + item.get('role_prompt','') + '\n')
    (ws / 'TOOLS.md').write_text('Use only STRATEGOS REST skills via strategos-core. No direct DB access.\n')
print('Applied strategos agents:', len(strategos_entries))
PY
/home/ubuntu/.npm-global/bin/openclaw agents list --json
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
