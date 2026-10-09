$ErrorActionPreference = 'Stop'
$PSNativeCommandUseErrorActionPreference = $true
$root = Split-Path $PSScriptRoot -Parent
Set-Location -LiteralPath $root
$env:PATH = "$root/.tools;$env:PATH"
Write-Host 'PLATFORM DELIVERY LAB | live Kubernetes run | GIF replay at 3x speed' -ForegroundColor Cyan
Write-Host 'Candidate gates: requests >= 20 | error rate < 2% | p95 < 300 ms'
& ./.venv/Scripts/python.exe -u scripts/demo.py --output docs/evidence/demo
