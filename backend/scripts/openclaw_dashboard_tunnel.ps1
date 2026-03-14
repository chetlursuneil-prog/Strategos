param(
    [Parameter(Mandatory = $true)]
    [string]$KeyPath,

    [string]$RemoteHost = "51.20.64.59",
    [string]$User = "ubuntu",
    [int]$LocalPort = 18789,
    [int]$RemotePort = 18789
)

$ErrorActionPreference = "Stop"

Write-Host "Starting SSH tunnel..."
Write-Host "Open this URL in your browser after tunnel connects:"
Write-Host "  http://localhost:$LocalPort/__openclaw__/canvas/"
Write-Host "If needed, try:"
Write-Host "  http://localhost:$LocalPort/__openclaw__/canvas/#/agents"
Write-Host ""
Write-Host "Press Ctrl+C to stop the tunnel."

ssh -N -L "${LocalPort}:127.0.0.1:${RemotePort}" -o StrictHostKeyChecking=no -i $KeyPath "${User}@${RemoteHost}"
