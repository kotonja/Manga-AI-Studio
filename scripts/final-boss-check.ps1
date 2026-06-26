$ErrorActionPreference = "Stop"

Set-Location (Resolve-Path (Join-Path $PSScriptRoot ".."))

$results = "docs/FINAL_BOSS_RESULTS.md"
$logDir = "evidence/final_boss_demo/logs"
$pgUser = if ($env:POSTGRES_USER) { $env:POSTGRES_USER } else { "manga" }
$pgPass = if ($env:POSTGRES_PASSWORD) { $env:POSTGRES_PASSWORD } else { "manga" }

New-Item -ItemType Directory -Force -Path $logDir | Out-Null
New-Item -ItemType Directory -Force -Path "docs" | Out-Null

@"
# Final Boss Results

Generated at: $((Get-Date).ToUniversalTime().ToString("yyyy-MM-ddTHH:mm:ssZ"))

## Command Results

| Gate | Status | Log |
| --- | --- | --- |
"@ | Set-Content -Encoding UTF8 -Path $results

function Add-Result {
    param(
        [string]$Name,
        [string]$Status,
        [string]$LogFile
    )
    Add-Content -Encoding UTF8 -Path $results -Value "| $Name | $Status | ``$LogFile`` |"
}

function Test-Url {
    param([string]$Url)
    $previous = $ErrorActionPreference
    $ErrorActionPreference = "Continue"
    curl.exe -fsS $Url > $null 2> $null
    $code = $LASTEXITCODE
    $ErrorActionPreference = $previous
    return $code -eq 0
}

function Run-Gate {
    param(
        [string]$Name,
        [scriptblock]$Script
    )
    $logFile = Join-Path $logDir "$Name.log"
    $global:LASTEXITCODE = 0
    $previous = $ErrorActionPreference
    $ErrorActionPreference = "Continue"
    try {
        & $Script *> $logFile
        if ($LASTEXITCODE -ne 0) {
            throw "Exit code $LASTEXITCODE"
        }
        $ErrorActionPreference = $previous
        Add-Result -Name $Name -Status "PASS" -LogFile $logFile
    }
    catch {
        $ErrorActionPreference = $previous
        Add-Result -Name $Name -Status "FAIL" -LogFile $logFile
        Write-Host "Final Boss gate failed: $Name"
        Write-Host "See $logFile"
        throw
    }
}

Run-Gate "compose-build" { docker compose build api web worker }
Run-Gate "compose-up" { docker compose up -d postgres redis minio minio-init api worker web }
Run-Gate "wait-api" {
    $ok = $false
    for ($i = 0; $i -lt 60; $i++) {
        if (Test-Url "http://localhost:8000/health") {
            $ok = $true
            break
        }
        Start-Sleep -Seconds 2
    }
    if (-not $ok) { throw "API did not become healthy in time." }
}
Run-Gate "health-api" { curl.exe -fsS http://localhost:8000/health }
Run-Gate "health-db" { curl.exe -fsS http://localhost:8000/health/db }
Run-Gate "health-redis" { curl.exe -fsS http://localhost:8000/health/redis }
Run-Gate "health-storage" { curl.exe -fsS http://localhost:8000/health/storage }
Run-Gate "health-worker" { curl.exe -fsS http://localhost:8000/health/worker }
Run-Gate "frontend-start" { curl.exe -fsS http://localhost:3000/ }

Run-Gate "migration-empty-drop" { docker compose exec -T postgres dropdb -U $pgUser --if-exists final_boss_migration_check }
Run-Gate "migration-empty-create" { docker compose exec -T postgres createdb -U $pgUser final_boss_migration_check }
Run-Gate "migration-empty-upgrade" {
    docker compose run --rm --no-deps `
        -e "DATABASE_URL=postgresql+psycopg://${pgUser}:${pgPass}@postgres:5432/final_boss_migration_check" `
        api sh -lc "alembic upgrade head"
}

Run-Gate "backend-tests" {
    docker compose run --rm --no-deps -e ENABLE_BACKGROUND_JOBS=false api sh -lc "python -m pip install -e /app/services/api[test] >/dev/null && pytest -q"
}
Run-Gate "frontend-typecheck" {
    docker compose run --rm --no-deps web sh -lc "pnpm install >/dev/null && pnpm --filter @manga-ai/web typecheck"
}
Run-Gate "frontend-build" {
    docker compose run --rm --no-deps web sh -lc "pnpm install >/dev/null && pnpm --filter @manga-ai/web build"
}
Run-Gate "frontend-restart-after-build" { docker compose up -d --force-recreate web }
Run-Gate "wait-frontend-after-build" {
    $ok = $false
    for ($i = 0; $i -lt 60; $i++) {
        if (Test-Url "http://localhost:3000/") {
            $ok = $true
            break
        }
        Start-Sleep -Seconds 2
    }
    if (-not $ok) { throw "Frontend did not become healthy after build/restart." }
}
Run-Gate "worker-import" {
    docker compose run --rm --no-deps worker sh -lc "python - <<'PY'
from manga_worker.tasks import director_generate_draft, mock_render_panel, render_panel
assert render_panel.name == 'manga_worker.render_panel'
assert mock_render_panel.name == 'manga_worker.mock_render_panel'
assert director_generate_draft.name == 'manga_worker.director_generate_draft'
print('worker import ok')
PY"
}

Run-Gate "final-demo" { & (Join-Path $PSScriptRoot "final-boss-demo.ps1") }
Run-Gate "final-export" { & (Join-Path $PSScriptRoot "final-boss-export.ps1") }
Run-Gate "final-inventory" {
    docker compose exec -T api python -m app.final_boss.run --inventory-only --skip-results-doc --repo-root /app/repo --output /app/evidence/final_boss_demo
}

@"

## Demo Evidence

- Evidence directory: `evidence/final_boss_demo/`
- Manifest: `evidence/final_boss_demo/export_manifest.json`
- Final pages: `evidence/final_boss_demo/final_pages/`
- Exports: `evidence/final_boss_demo/exports/`

## Notes

- Real OpenAI and ComfyUI calls were not required for this check.
- Mock providers are deterministic and are the expected local/test path.
- See `docs/STUBS_AND_TODOS.md` for documented provider stubs and placeholder areas.
"@ | Add-Content -Encoding UTF8 -Path $results

Write-Host "Final Boss check passed. Results written to $results"
