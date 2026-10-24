$ErrorActionPreference = 'Stop'
$previousDebug = $env:DJANGO_DEBUG
$previousDatabaseBackend = $env:DATABASE_BACKEND
Push-Location $PSScriptRoot
try {
    $env:DJANGO_DEBUG = 'true'
    $env:DATABASE_BACKEND = 'sqlite'
    $python = "$PSScriptRoot\.venv\Scripts\python.exe"
    & $python manage.py check
    if ($LASTEXITCODE -ne 0) { throw 'Django check failed.' }
    & $python manage.py makemigrations --check --dry-run
    if ($LASTEXITCODE -ne 0) { throw 'Unexpected model changes.' }
    & $python manage.py migrate --check
    if ($LASTEXITCODE -ne 0) { throw 'Unapplied database migrations.' }
    & $python manage.py test portal.tests --verbosity 0
    if ($LASTEXITCODE -ne 0) { throw 'Acceptance tests failed.' }
    & $python scripts\evaluate_release.py --output data\release-evaluation.json
    if ($LASTEXITCODE -ne 0) { throw 'Synthetic evaluation contract failed.' }
    & $python manage.py due_actions --as-of 2026-10-23
    if ($LASTEXITCODE -ne 0) { throw 'Due-action report failed.' }
} finally { $env:DJANGO_DEBUG = $previousDebug; $env:DATABASE_BACKEND = $previousDatabaseBackend; Pop-Location }
