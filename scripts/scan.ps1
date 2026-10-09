param([string]$Tag = 'local')
$ErrorActionPreference = 'Stop'
$PSNativeCommandUseErrorActionPreference = $true
Set-Location -LiteralPath (Split-Path $PSScriptRoot -Parent)
New-Item -ItemType Directory -Force artifacts | Out-Null
docker volume create platform-delivery-lab-trivy-cache | Out-Null
foreach ($service in @('ticket-api','notification-worker','web-frontend')) {
    $image = "ghcr.io/iamnajib71/platform-delivery-lab/${service}:$Tag"
    docker save --output "artifacts/$service.tar" $image
    docker run --rm -v platform-delivery-lab-trivy-cache:/root/.cache/ -v "${PWD}/artifacts:/out" aquasec/trivy:0.75.0 image --input "/out/$service.tar" --scanners vuln --severity HIGH,CRITICAL --ignore-unfixed --exit-code 1 --format json --output "/out/$service-trivy.json"
    docker run --rm -v "${PWD}/artifacts:/out" anchore/syft:v1.54.1 "docker-archive:/out/$service.tar" -o "spdx-json=/out/$service-sbom.spdx.json"
}
