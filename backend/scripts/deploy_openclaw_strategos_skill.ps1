param(
    [Parameter(Mandatory = $true)]
    [string]$RemoteHost,

    [Parameter(Mandatory = $true)]
    [string]$KeyPath,

    [string]$User = "ubuntu"
)

$ErrorActionPreference = "Stop"

$repoRoot = Split-Path -Parent $PSScriptRoot
$localSkillDir = Join-Path $repoRoot "openclaw\workspace_skills\strategos-core"

if (-not (Test-Path $localSkillDir)) {
    throw "Local skill folder not found: $localSkillDir"
}

$remoteTmp = "/tmp/strategos-core"
$remoteTarget = "/home/ubuntu/.openclaw/workspace/skills/strategos-core"

Write-Host "[1/4] Preparing remote directories..."
ssh -o StrictHostKeyChecking=no -i $KeyPath "${User}@${RemoteHost}" "mkdir -p /home/ubuntu/.openclaw/workspace/skills"

Write-Host "[2/4] Uploading STRATEGOS skill namespace to temp path..."
scp -o StrictHostKeyChecking=no -i $KeyPath -r $localSkillDir "${User}@${RemoteHost}:${remoteTmp}"

Write-Host "[3/4] Replacing only STRATEGOS namespace on EC2..."
$remoteReplaceCmd = "rm -rf '$remoteTarget' && mkdir -p '/home/ubuntu/.openclaw/workspace/skills' && mv '$remoteTmp' '$remoteTarget'"
ssh -o StrictHostKeyChecking=no -i $KeyPath "${User}@${RemoteHost}" $remoteReplaceCmd

Write-Host "[4/4] Validating loaded skills..."
ssh -o StrictHostKeyChecking=no -i $KeyPath "${User}@${RemoteHost}" "/home/ubuntu/.npm-global/bin/openclaw skills list | grep -i strategos || true"

Write-Host "Done. Updated namespace: $remoteTarget"
