param(
    [Parameter(Mandatory = $true)]
    [string]$RemoteHost,

    [Parameter(Mandatory = $true)]
    [string]$KeyPath,

    [Parameter(Mandatory = $true)]
    [string]$DatabaseUrl,

    [Parameter(Mandatory = $true)]
    [string]$SupabaseServiceRoleKey,

    [Parameter(Mandatory = $true)]
    [string]$SecretKey,

    [string]$User = "ubuntu"
)

$ErrorActionPreference = "Stop"

$repoRoot = Split-Path -Parent $PSScriptRoot
$remoteRoot = "~/strategos-backend"

Write-Host "[1/6] Ensure remote directory exists..."
ssh -o StrictHostKeyChecking=no -i $KeyPath "${User}@${RemoteHost}" "mkdir -p $remoteRoot"

Write-Host "[2/6] Upload backend source..."
scp -o StrictHostKeyChecking=no -i $KeyPath "$repoRoot\requirements.txt" "${User}@${RemoteHost}:${remoteRoot}/"
scp -o StrictHostKeyChecking=no -i $KeyPath "$repoRoot\alembic.ini" "${User}@${RemoteHost}:${remoteRoot}/"
scp -o StrictHostKeyChecking=no -i $KeyPath -r "$repoRoot\app" "${User}@${RemoteHost}:${remoteRoot}/"
scp -o StrictHostKeyChecking=no -i $KeyPath -r "$repoRoot\alembic" "${User}@${RemoteHost}:${remoteRoot}/"
scp -o StrictHostKeyChecking=no -i $KeyPath -r "$repoRoot\scripts" "${User}@${RemoteHost}:${remoteRoot}/"

Write-Host "[3/6] Upload EC2 bootstrap script..."
scp -o StrictHostKeyChecking=no -i $KeyPath "$repoRoot\scripts\bootstrap_strategos_ec2.sh" "${User}@${RemoteHost}:${remoteRoot}/scripts/"

Write-Host "[4/6] Write remote env file..."
$remoteEnv = @"
DATABASE_URL=$DatabaseUrl
SUPABASE_SERVICE_ROLE_KEY=$SupabaseServiceRoleKey
SECRET_KEY=$SecretKey
ENV=production
REDIS_URL=redis://localhost:6379/0
"@
$remoteEnvB64 = [Convert]::ToBase64String([Text.Encoding]::UTF8.GetBytes($remoteEnv))
ssh -o StrictHostKeyChecking=no -i $KeyPath "${User}@${RemoteHost}" "mkdir -p ~/.config/strategos && echo '$remoteEnvB64' | base64 -d > ~/.config/strategos/strategos.env"

Write-Host "[5/6] Bootstrap API service on EC2..."
ssh -o StrictHostKeyChecking=no -i $KeyPath "${User}@${RemoteHost}" "chmod +x ${remoteRoot}/scripts/bootstrap_strategos_ec2.sh && bash ${remoteRoot}/scripts/bootstrap_strategos_ec2.sh"

Write-Host "[6/6] Validate service..."
ssh -o StrictHostKeyChecking=no -i $KeyPath "${User}@${RemoteHost}" "curl -sS -i http://127.0.0.1:8000/api/v1/health"

Write-Host "Done. STRATEGOS backend deployed on $RemoteHost"
