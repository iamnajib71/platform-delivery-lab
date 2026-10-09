#!/usr/bin/env bash
set -euo pipefail
tag="${1:-local}"
mkdir -p artifacts
docker volume create platform-delivery-lab-trivy-cache >/dev/null
for service in ticket-api notification-worker web-frontend; do
  image="ghcr.io/iamnajib71/platform-delivery-lab/${service}:${tag}"
  docker run --rm -v /var/run/docker.sock:/var/run/docker.sock \
    -v platform-delivery-lab-trivy-cache:/root/.cache/ \
    -v "$PWD/artifacts:/out" aquasec/trivy:0.75.0 image \
    --scanners vuln --severity HIGH,CRITICAL --ignore-unfixed --exit-code 1 \
    --format json --output "/out/${service}-trivy.json" "$image"
  docker run --rm -v /var/run/docker.sock:/var/run/docker.sock \
    -v "$PWD/artifacts:/out" anchore/syft:v1.54.1 "$image" \
    -o "spdx-json=/out/${service}-sbom.spdx.json"
done
