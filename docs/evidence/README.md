# Actual run evidence

Recorded on 10 October 2026 (Australia/Sydney). Raw Kubernetes timestamps use UTC.

| Check | Measured result | Source |
|---|---|---|
| Unit and contract tests | 12 passed, 0 failures | [JUnit](tests.xml) |
| Good candidate | 10%, 50%, 100%; 2 Successful AnalysisRuns | [Timeline](demo/good-142944-timeline.json) |
| Good p95 latency | 4.75–4.93 ms across gate samples | [Analysis](demo/good-142944-analysis.json) |
| Injected candidate error rate | 100% → Failed → automatic abort | [Analysis](demo/bad-142944-analysis.json) |
| Post-abort traffic | 0% canary; 30/30 HTTP 200 from stable release | [Summary](demo/summary.json) |
| ticket-api image | 0 fixable HIGH/CRITICAL; 131 SPDX packages | [Trivy](ticket-api-trivy.json), [SBOM](ticket-api-sbom.spdx.json) |
| notification-worker image | 0 fixable HIGH/CRITICAL; 131 SPDX packages | [Trivy](notification-worker-trivy.json), [SBOM](notification-worker-sbom.spdx.json) |
| web-frontend image | 0 fixable HIGH/CRITICAL; 131 SPDX packages | [Trivy](web-frontend-trivy.json), [SBOM](web-frontend-sbom.spdx.json) |

[Controller log](demo/controller.log) · [Kubernetes events](demo/events.txt) · [Machine-readable results](results.json)

The intentional bad template remains visible and the Rollout is Degraded; traffic has returned to the healthy ReplicaSet. No manual abort command was used in the demo.

Scans used Trivy 0.75.0 with `--severity HIGH,CRITICAL --ignore-unfixed`; this reports the gated subset, not every known vulnerability. Syft 1.54.1 created the original SPDX JSON files.

## Verification from an empty cluster

The final Windows checkout ran `pwsh -NoProfile -File scripts/lab.ps1 up` successfully:
Terraform created all five resources, 12 tests passed, images were scanned, ticket-to-worker
smoke tests passed, both canary scenarios completed, 30/30 recovery requests used the stable
release, and `CanaryDegraded` fired. The alert job scrapes both controller pods to observe
the leader consistently.

[Complete command output](windows-clean-clone/run.log) ·
[Validation metadata](windows-clean-clone/validation.json) ·
[Rollout summary](windows-clean-clone/summary.json) ·
[Actual firing alerts](windows-clean-clone/alerts.json) ·
[Windows JUnit](windows-clean-clone/tests.xml) ·
[Linux/Python 3.12 tests](linux-tests.txt) ·
[Tracked-source secret scan: 0 findings](source-secret-scan.json)
