$ErrorActionPreference = "Stop"

Set-Location (Resolve-Path (Join-Path $PSScriptRoot ".."))

& (Join-Path $PSScriptRoot "final-boss-demo.ps1")

$zipFiles = @(Get-ChildItem -Path "evidence/final_boss_demo/exports" -Filter "*.zip" -File -ErrorAction SilentlyContinue)
$pdfFiles = @(Get-ChildItem -Path "evidence/final_boss_demo/exports" -Filter "*.pdf" -File -ErrorAction SilentlyContinue)

if ($zipFiles.Count -lt 1) {
    throw "Final Boss export check failed: no ZIP export file found."
}

if ($pdfFiles.Count -lt 1) {
    throw "Final Boss export check failed: no PDF export file found."
}

Write-Host "Final Boss export files verified in evidence/final_boss_demo/exports"
