param([ValidateSet('up', 'test', 'demo', 'down')][string]$Action = 'up')
$ErrorActionPreference = 'Stop'
$PSNativeCommandUseErrorActionPreference = $true
$root = Split-Path $PSScriptRoot -Parent
Set-Location -LiteralPath $root
& "$PSScriptRoot/bootstrap.ps1"
$env:KUBECONFIG = "$root/.kube/config"
$env:HELM_CACHE_HOME = "$root/.tools/helm/cache"
$env:HELM_CONFIG_HOME = "$root/.tools/helm/config"
$env:HELM_DATA_HOME = "$root/.tools/helm/data"
New-Item -ItemType Directory -Force .kube,artifacts | Out-Null
if ($Action -eq 'down') {
    terraform -chdir=infra destroy -auto-approve
    return
}
if (!(Test-Path .venv/Scripts/python.exe)) { python -m venv .venv }
$python = "$root/.venv/Scripts/python.exe"
& $python -m pip install -q -r requirements-dev.txt
& $python -m ruff check services tests scripts
& $python -m ruff format --check services tests scripts
& $python -m pytest -q --junitxml=artifacts/tests.xml
if ($Action -eq 'test') { return }
if ($Action -eq 'up') {
    docker version
    terraform -chdir=infra init
    terraform -chdir=infra validate
    terraform -chdir=infra plan '-out=lab.tfplan'
    terraform -chdir=infra apply lab.tfplan
    foreach ($service in @('ticket-api', 'notification-worker', 'web-frontend')) {
        $module = $service.Replace('-', '_')
        docker build --build-arg "SERVICE=$module" -t "ghcr.io/iamnajib71/platform-delivery-lab/${service}:local" .
    }
    & "$PSScriptRoot/scan.ps1"
    & $python scripts/deploy.py --load
    & $python scripts/smoke.py
}
& $python scripts/demo.py
Write-Host 'Console: http://localhost:8088'
Write-Host 'Grafana: http://localhost:3008/d/lab/platform-delivery-lab'
