# Downloads tools only into this checkout. Requires Docker Desktop in Linux container mode.
$ErrorActionPreference = 'Stop'
$root = Split-Path $PSScriptRoot -Parent
$toolDir = Join-Path $root '.tools'
New-Item -ItemType Directory -Force $toolDir | Out-Null
function Fetch($url, $name) {
    $path = Join-Path $toolDir $name
    if (!(Test-Path -LiteralPath $path)) { Invoke-WebRequest $url -OutFile $path }
    return $path
}
if (!(Test-Path "$toolDir/terraform.exe")) {
    $zip = Fetch 'https://releases.hashicorp.com/terraform/1.13.5/terraform_1.13.5_windows_amd64.zip' 'terraform.zip'
    $sums = Fetch 'https://releases.hashicorp.com/terraform/1.13.5/terraform_1.13.5_SHA256SUMS' 'terraform.sha256'
    $expected = ((Get-Content $sums | Where-Object { $_ -match 'terraform_1.13.5_windows_amd64.zip$' }) -split '\s+')[0]
    if ((Get-FileHash $zip -Algorithm SHA256).Hash.ToLower() -ne $expected) { throw 'Terraform checksum mismatch' }
    Expand-Archive -LiteralPath $zip -DestinationPath $toolDir -Force
}
if (!(Test-Path "$toolDir/kind.exe")) {
    $exe = Fetch 'https://github.com/kubernetes-sigs/kind/releases/download/v0.33.0/kind-windows-amd64' 'kind.exe'
    $sums = Fetch 'https://github.com/kubernetes-sigs/kind/releases/download/v0.33.0/kind-windows-amd64.sha256sum' 'kind.sha256'
    $expected = ((Get-Content $sums) -split '\s+')[0]
    if ((Get-FileHash $exe -Algorithm SHA256).Hash.ToLower() -ne $expected) { throw 'kind checksum mismatch' }
}
if (!(Test-Path "$toolDir/helm.exe")) {
    $archive = Fetch 'https://get.helm.sh/helm-v3.17.3-windows-amd64.zip' 'helm.zip'
    $sums = Fetch 'https://get.helm.sh/helm-v3.17.3-windows-amd64.zip.sha256sum' 'helm.sha256'
    $expected = ((Get-Content $sums) -split '\s+')[0]
    if ((Get-FileHash $archive -Algorithm SHA256).Hash.ToLower() -ne $expected) { throw 'Helm checksum mismatch' }
    Expand-Archive -LiteralPath $archive -DestinationPath $toolDir -Force
    Copy-Item "$toolDir/windows-amd64/helm.exe" "$toolDir/helm.exe"
}
$env:PATH = "$toolDir;$env:PATH"
Write-Host 'Local tools ready: Terraform 1.13.5, kind 0.33.0, Helm 3.17.3'
