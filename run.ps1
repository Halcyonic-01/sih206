# Build the React app and start the portal on one port.
# Usage: .\run.ps1 [--port 8010] [--dev] [--prod] [--smoke] [--skip-build] [--seed]
param([string]$Python = 'py', [Parameter(ValueFromRemainingArguments = $true)][string[]]$Rest)
$ErrorActionPreference = 'Stop'
Push-Location $PSScriptRoot
try {
    $venvPython = Join-Path $PSScriptRoot '.venv\Scripts\python.exe'
    if (Test-Path $venvPython) {
        & $venvPython scripts\run_portal.py @Rest
    } elseif ($Python -eq 'py') {
        & py -3.12 scripts\run_portal.py @Rest
    } else {
        & $Python scripts\run_portal.py @Rest
    }
    if ($LASTEXITCODE -ne 0) { throw 'The portal stopped with an error.' }
} finally { Pop-Location }
