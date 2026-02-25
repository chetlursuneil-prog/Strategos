param(
    [Parameter(Mandatory = $true)]
    [string]$RemoteHost,

    [Parameter(Mandatory = $true)]
    [string]$KeyPath,

    [string]$User = "ubuntu"
)

$ErrorActionPreference = "Stop"
$remoteTarget = "/home/ubuntu/.openclaw/workspace/skills/strategos-core"

Write-Host "Removing only STRATEGOS namespace: $remoteTarget"
ssh -o StrictHostKeyChecking=no -i $KeyPath "${User}@${RemoteHost}" "rm -rf '$remoteTarget'"

Write-Host "Current STRATEGOS skill entries after removal:"
ssh -o StrictHostKeyChecking=no -i $KeyPath "${User}@${RemoteHost}" "/home/ubuntu/.npm-global/bin/openclaw skills list | grep -i strategos || true"

Write-Host "Done."
