param([Parameter(Mandatory=$true)][ValidateSet('database','provision','migrate','seed','backend','frontend','test','validate','status','worker','simulator')][string]$Action)
$ErrorActionPreference = 'Stop'
$projectRoot = Split-Path -Parent $PSScriptRoot
Set-Location -LiteralPath $projectRoot
$pythonExe = Join-Path $projectRoot '.venv/Scripts/python.exe'
if (-not (Test-Path -LiteralPath $pythonExe)) { throw 'Create .venv with Python 3.12 first. See README.md.' }
$env:PYTHONPATH = Join-Path $projectRoot 'services/backend'
$env:PYTHONIOENCODING = 'utf-8'
$env:TEMP = Join-Path $projectRoot '.cache/tmp'
$env:TMP = $env:TEMP
New-Item -ItemType Directory -Force -Path $env:TEMP | Out-Null
$composeArgs = @('compose','--env-file','.env','-f','deploy/compose.yaml')
$priorPath = $env:PATH
try {
    if ($Action -in @('database','status')) {
        $dockerCommand = Get-Command docker.exe -ErrorAction SilentlyContinue
        $dockerExe = if ($dockerCommand) { $dockerCommand.Source } else { Join-Path $env:LOCALAPPDATA 'Programs/DockerDesktop/resources/bin/docker.exe' }
        if (-not (Test-Path -LiteralPath $dockerExe)) { throw 'Docker CLI not found; use its installed absolute path.' }
        # Needed for the credential helper; restored below, never changes Windows PATH.
        $env:PATH = (Split-Path -Parent $dockerExe) + [IO.Path]::PathSeparator + $priorPath
    }
    switch ($Action) {
        database { & $dockerExe @composeArgs up -d --wait db }
        status { & $dockerExe @composeArgs ps }
        provision { & $pythonExe tools/provision_database.py roles }
        migrate {
            & $pythonExe -m alembic -c services/backend/alembic.ini upgrade head
            if ($LASTEXITCODE -eq 0) { & $pythonExe tools/provision_database.py grants }
        }
        seed { & $pythonExe -m app.seed }
        backend { & $pythonExe -m uvicorn app.main:create_app --factory --host 127.0.0.1 --port 8000 --no-access-log --no-proxy-headers }
        worker { & $pythonExe -m app.workers.device }
        simulator { & $pythonExe -m simulators.device.main }
        frontend { & npm.cmd --prefix apps/web run dev }
        test { & $pythonExe -m pytest -q --basetemp=.cache/pytest-tmp --junitxml=docs/PHASE5_REGRESSION.xml }
        validate { & $pythonExe tools/validate_contracts.py docs/CONTRACT_VALIDATION.json }
    }
    if ($LASTEXITCODE -ne 0) { throw "Action $Action failed (exit $LASTEXITCODE)." }
} finally { $env:PATH = $priorPath }
