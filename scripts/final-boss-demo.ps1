$ErrorActionPreference = "Stop"

Set-Location (Resolve-Path (Join-Path $PSScriptRoot ".."))
New-Item -ItemType Directory -Force -Path "evidence" | Out-Null

function Test-Url {
    param([string]$Url)
    $previous = $ErrorActionPreference
    $ErrorActionPreference = "Continue"
    curl.exe -fsS $Url > $null 2> $null
    $code = $LASTEXITCODE
    $ErrorActionPreference = $previous
    return $code -eq 0
}

function Invoke-Native {
    param([scriptblock]$Script)
    $previous = $ErrorActionPreference
    $ErrorActionPreference = "Continue"
    & $Script
    $code = $LASTEXITCODE
    $ErrorActionPreference = $previous
    if ($code -ne 0) { throw "Native command failed with exit code $code" }
}

Invoke-Native { docker compose up -d postgres redis minio minio-init api }

Write-Host "Waiting for API health..."
$ok = $false
for ($i = 0; $i -lt 60; $i++) {
    if (Test-Url "http://localhost:8000/health") {
        $ok = $true
        break
    }
    Start-Sleep -Seconds 2
}
if (-not $ok) { throw "API did not become healthy in time." }

Invoke-Native {
    docker compose exec -T api python -m app.final_boss.run `
        --demo-only `
        --repo-root /app/repo `
        --output /app/evidence/final_boss_demo
}

Write-Host "Final Boss demo evidence written to evidence/final_boss_demo"
