# Rollback and incident response

Run from the checkout in PowerShell 7. All commands explicitly use the lab kubeconfig.

1. Confirm impact: open the console at http://localhost:8088 and Grafana at
   http://localhost:3008/d/lab/platform-delivery-lab. Inspect error rate and p95 by release.
2. Capture evidence before changing anything:

   ```powershell
   kubectl --kubeconfig .kube/config -n delivery-lab get rollout ticket-api -o yaml
   kubectl --kubeconfig .kube/config -n delivery-lab get analysisrun -o yaml
   kubectl --kubeconfig .kube/config -n delivery-lab get events --sort-by=.lastTimestamp
   kubectl --kubeconfig .kube/config -n argo-rollouts logs deployment/argo-rollouts --since=10m
   ```

3. Failed analysis sets `status.abort: true` and ingress canary weight to **0**. Argo
   retains the healthy ReplicaSet and automatically restores stable traffic. The Rollout
   stays Degraded to make the rejected release visible; its desired pod template still
   describes the faulty release. This is traffic rollback, not a Git revert.
4. If analysis has not acted and users are affected, explicitly abort the canary:

   ```powershell
   kubectl --kubeconfig .kube/config -n delivery-lab patch rollout ticket-api --type=merge -p '{"status":{"abort":true}}' --subresource=status
   ```

   Prefer the official plugin when installed:
   `kubectl --kubeconfig .kube/config argo rollouts abort ticket-api -n delivery-lab`.
   To restore the desired template too, use
   `kubectl --kubeconfig .kube/config argo rollouts undo ticket-api -n delivery-lab`.
   Do not promote a candidate whose metrics are missing or failing.
5. Verify ingress canary weight is 0 and `/api/tickets` returns HTTP 200 from the stable
   release. Run `python scripts/smoke.py` with the active virtual environment.
6. Investigate `X-Request-ID` in JSON request logs, the failed AnalysisRun metric values,
   pod readiness, resource pressure, and worker errors. Fix the release, run tests and
   scans, then deploy a new immutable image tag through CI.

## Alert behavior

Prometheus evaluates the checked-in rules every 5 seconds: errors above 2% for 15s,
p95 above 300ms for 30s, a failed scrape for 30s, and a Degraded canary for 5s.
The alerts are visible at http://localhost:9098/alerts. There is no external paging
receiver or email delivery; this free lab deliberately has no third-party secrets.

Argo's metrics job discovers each controller pod separately. Scraping the shared metrics
Service can land on a follower with no rollout state. The abort alert accepts both `Abort`
and `Degraded` metric phases to cover the controller's phase vocabulary.

## Reset

`pwsh -File scripts/lab.ps1 down` destroys only the Terraform-managed lab cluster.
Other Docker containers are untouched. `pwsh -File scripts/lab.ps1 up` recreates the
platform, runs tests, builds and deploys services, and repeats both rollout scenarios.
