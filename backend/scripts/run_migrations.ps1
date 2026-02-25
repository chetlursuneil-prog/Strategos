param(
    [string]$DatabaseUrl
)

$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Definition
$projectRoot = Resolve-Path (Join-Path $scriptDir "..")
Set-Location $projectRoot

Write-Host "Running migration helper in $projectRoot"

# Load backend/.env if present
$envFile = Join-Path $projectRoot ".env"
if (Test-Path $envFile) {
    Write-Host "Loading environment variables from $envFile"
    Get-Content $envFile | ForEach-Object {
        $_ = $_.Trim()
        if ($_ -and -not $_.StartsWith('#')) {
            $parts = $_ -split('=',2)
            if ($parts.Count -eq 2) {
                $key = $parts[0].Trim()
                $value = $parts[1].Trim().Trim('"')
                [System.Environment]::SetEnvironmentVariable($key, $value, 'Process')
                Write-Host "Set $key"
            }
        }
    }
}

# Resolve DATABASE_URL if it uses a variable placeholder form like ${SUPABASE_DB_URL}
if ($env:DATABASE_URL -and $env:DATABASE_URL -match '^\$\{([A-Za-z_][A-Za-z0-9_]*)\}$') {
    $refKey = $Matches[1]
    $refVal = [System.Environment]::GetEnvironmentVariable($refKey, 'Process')
    if ($refVal) {
        [System.Environment]::SetEnvironmentVariable('DATABASE_URL', $refVal, 'Process')
        Write-Host "Resolved DATABASE_URL from $refKey"
    }
}

if ($DatabaseUrl) {
    [System.Environment]::SetEnvironmentVariable('DATABASE_URL', $DatabaseUrl, 'Process')
    Write-Host "DATABASE_URL set from parameter"
}

if (-not $env:DATABASE_URL) {
    Write-Host "ERROR: DATABASE_URL not set. Provide -DatabaseUrl or create backend/.env" -ForegroundColor Red
    exit 1
}

Write-Host "DATABASE_URL is set (value hidden)"

# Activate venv if present
$venvActivate = Join-Path $projectRoot ".venv\Scripts\Activate.ps1"
if (Test-Path $venvActivate) {
    Write-Host "Activating virtualenv"
    . $venvActivate
} else {
    Write-Host ".venv not found. Please create virtualenv or run this script from an activated venv." -ForegroundColor Yellow
}

# Run alembic
$alembicExe = Join-Path $projectRoot ".venv\Scripts\alembic.exe"
if (Test-Path $alembicExe) {
    Write-Host "Running: alembic -c alembic.ini upgrade head"
    & $alembicExe -c alembic.ini upgrade head
    $exitCode = $LASTEXITCODE
} else {
    Write-Host "alembic.exe not found in venv, trying 'python -m alembic'"
    python -m alembic -c alembic.ini upgrade head
    $exitCode = $LASTEXITCODE
}

if ($exitCode -ne 0) {
    Write-Host "Migration failed with exit code $exitCode" -ForegroundColor Red
    exit $exitCode
}

Write-Host "Migration completed successfully." -ForegroundColor Green
