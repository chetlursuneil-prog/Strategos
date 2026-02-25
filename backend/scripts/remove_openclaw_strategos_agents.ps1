param(
    [Parameter(Mandatory = $true)]
    [string]$RemoteHost,

    [Parameter(Mandatory = $true)]
    [string]$KeyPath,

    [string]$User = "ubuntu"
)

$ErrorActionPreference = "Stop"

$remoteScript = @'
set -euo pipefail
python3 - <<"PY"
import json
from pathlib import Path
cfg_path = Path('/home/ubuntu/.openclaw/openclaw.json')
cfg = json.loads(cfg_path.read_text())
if isinstance(cfg.get('agents'), dict) and isinstance(cfg['agents'].get('list'), list):
    cfg['agents']['list'] = [a for a in cfg['agents']['list'] if not (isinstance(a, dict) and str(a.get('id','')).startswith('strategos-'))]
cfg_path.write_text(json.dumps(cfg, indent=2) + '\n')
PY
rm -rf /home/ubuntu/.openclaw/workspaces/strategos
/home/ubuntu/.npm-global/bin/openclaw agents list --json
'@

$remoteScriptB64 = [Convert]::ToBase64String([Text.Encoding]::UTF8.GetBytes($remoteScript))

ssh -o StrictHostKeyChecking=no -i $KeyPath "${User}@${RemoteHost}" "echo '$remoteScriptB64' | base64 -d | tr -d '\r' | bash"
Write-Host "Removed isolated STRATEGOS agents (strategos-*)."
