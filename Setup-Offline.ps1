param([string]$Python = 'py')
$ErrorActionPreference = 'Stop'
if ($Python -eq 'py') {
    & $Python -3.12 "$PSScriptRoot\scripts\setup_offline.py"
} else {
    & $Python "$PSScriptRoot\scripts\setup_offline.py"
}
if ($LASTEXITCODE -ne 0) { throw 'Offline setup failed.' }
