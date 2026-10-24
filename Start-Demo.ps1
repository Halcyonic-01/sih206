param([ValidateRange(1024,65535)][int]$Port = 8000)
$ErrorActionPreference = 'Stop'
$previousDebug = $env:DJANGO_DEBUG
$previousDatabaseBackend = $env:DATABASE_BACKEND
Push-Location $PSScriptRoot
try {
    $env:DJANGO_DEBUG = 'true'
    $env:DATABASE_BACKEND = 'sqlite'
    & "$PSScriptRoot\.venv\Scripts\python.exe" manage.py runserver "127.0.0.1:$Port" --noreload
    if ($LASTEXITCODE -ne 0) { throw 'Demo server failed.' }
} finally { $env:DJANGO_DEBUG = $previousDebug; $env:DATABASE_BACKEND = $previousDatabaseBackend; Pop-Location }
