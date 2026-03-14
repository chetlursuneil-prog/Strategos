param(
    [Parameter(Mandatory = $true)]
    [ValidateSet("strategos-only", "integrated", "status")]
    [string]$Mode,

    [Parameter(Mandatory = $true)]
    [string]$RemoteHost,

    [Parameter(Mandatory = $true)]
    [string]$KeyPath,

    [string]$User = "ubuntu"
)

$ErrorActionPreference = "Stop"

$localScript = "backend/scripts/strategos_mode_switch.sh"
$remoteScriptDir = "~/strategos-backend/scripts"
$remoteScript = "$remoteScriptDir/strategos_mode_switch.sh"

ssh -o StrictHostKeyChecking=no -i $KeyPath "${User}@${RemoteHost}" "mkdir -p $remoteScriptDir"
scp -o StrictHostKeyChecking=no -i $KeyPath $localScript "${User}@${RemoteHost}:$remoteScript"
ssh -o StrictHostKeyChecking=no -i $KeyPath "${User}@${RemoteHost}" "chmod +x $remoteScript && $remoteScript $Mode"

