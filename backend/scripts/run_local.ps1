param(
    [switch]$StartFrontend,
    [switch]$RestartBackend
)

# Loads a .env file into the process environment (simple KEY=VALUE lines)
function Load-EnvFile($path) {
    if (-not (Test-Path $path)) { return }
    Get-Content $path | ForEach-Object {
        if ($_ -and ($_ -match '=')) {
            $pair = $_ -split('=',2)
            $key = $pair[0].Trim()
            $val = $pair[1].Trim()
            [System.Environment]::SetEnvironmentVariable($key, $val, 'Process')
        }
    }
}

$scriptDir = Split-Path -Path $MyInvocation.MyCommand.Path -Parent
$backendRoot = Resolve-Path (Join-Path $scriptDir "..")
$repoRoot = Resolve-Path (Join-Path $backendRoot "..")

Push-Location $backendRoot

Write-Host "Loading .env (if present)..."
Load-EnvFile (Join-Path $repoRoot ".env")
Load-EnvFile (Join-Path $backendRoot ".env")

if (Test-Path ".\.venv\Scripts\Activate.ps1") {
    Write-Host "Activating virtual environment..."
    . ".\.venv\Scripts\Activate.ps1"
} else {
    Write-Host "No .venv found at ./venv — make one with: python -m venv .venv and install requirements."
}

$listener = Get-NetTCPConnection -LocalPort 8000 -State Listen -ErrorAction SilentlyContinue | Select-Object -First 1
if ($listener) {
    $runningProcess = Get-CimInstance Win32_Process -Filter "ProcessId = $($listener.OwningProcess)" -ErrorAction SilentlyContinue
    $commandLine = if ($runningProcess) { $runningProcess.CommandLine } else { "" }

    if ($RestartBackend) {
        Write-Host "Restart requested. Stopping process on port 8000 (PID $($listener.OwningProcess))..."
        Stop-Process -Id $listener.OwningProcess -Force
        Start-Sleep -Seconds 1
    } elseif ($commandLine -like "*uvicorn app.main:app*") {
        Write-Host "Backend already running on http://localhost:8000 (PID $($listener.OwningProcess))."
        if ($StartFrontend) {
            Write-Host "Launching frontend in a new terminal..."
            $frontendCmd = "cd $repoRoot\frontend; npm install; npm run dev"
            Start-Process powershell -ArgumentList "-NoExit","-Command","$frontendCmd"
        }
        Pop-Location
        return
    } else {
        Write-Warning "Port 8000 is in use by PID $($listener.OwningProcess). Use -RestartBackend to stop it and continue."
        Pop-Location
        return
    }
}

Write-Host "Running Alembic migrations..."
try {
    alembic -c alembic.ini upgrade head
} catch {
    Write-Warning "Alembic migration failed: $_"
}

Write-Host "Starting backend (uvicorn) on http://localhost:8000"
python -m uvicorn app.main:app --host 127.0.0.1 --port 8000

if ($StartFrontend) {
    Write-Host "(Started backend in this window.) Launching frontend in a new terminal..."
    $frontendCmd = "cd ..\frontend; npm install; npm run dev"
    Start-Process powershell -ArgumentList "-NoExit","-Command","$frontendCmd"
}

Pop-Location
