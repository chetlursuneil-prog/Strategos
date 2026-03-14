param(
    [Parameter(Mandatory = $true)]
    [string]$KeyPath,

    [string]$RemoteHost = "51.20.64.59",
    [string]$User = "ubuntu",
    [int]$LocalPort = 18889
)

$ErrorActionPreference = "Stop"

$remote = @'
python3 - <<'PY'
import json
cfg = json.load(open('/home/ubuntu/.openclaw/openclaw.json', 'r', encoding='utf-8'))
token = (((cfg.get('gateway') or {}).get('auth') or {}).get('token') or '').strip()
print(token)
PY
'@

$token = (ssh -o StrictHostKeyChecking=no -i $KeyPath "${User}@${RemoteHost}" $remote).Trim()
if (-not $token) {
    throw "Could not read gateway token from /home/ubuntu/.openclaw/openclaw.json"
}

$ws = "ws://localhost:$LocalPort"
$u1 = "http://localhost:$LocalPort/chat?session=main&gatewayToken=$token&gatewayUrl=$([uri]::EscapeDataString($ws))"
$u2 = "http://localhost:$LocalPort/chat?session=main&token=$token&url=$([uri]::EscapeDataString($ws))"
$u3 = "http://localhost:$LocalPort/chat?session=main"

Write-Host "Token:"
Write-Host "  $token"
Write-Host ""
Write-Host "Try these URLs in order (while tunnel is running):"
Write-Host "  $u1"
Write-Host "  $u2"
Write-Host "  $u3"
Write-Host ""
Write-Host "If chat page still shows unauthorized, open DevTools Console and run:"
Write-Host "  localStorage.setItem('gatewayToken', '$token'); localStorage.setItem('gatewayUrl', '$ws'); location.reload();"

