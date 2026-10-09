"""Exercise real Argo analysis. Assert promotion, abort, routing, and stable recovery."""

import argparse
import json
import sys
import time
import urllib.request
from datetime import UTC, datetime
from pathlib import Path

from deploy import ROOT, kube


def object_get(kind, name):
    return json.loads(kube("-n", "delivery-lab", "get", kind, name, "-o", "json"))


def patch_release(release, inject):
    container = object_get("rollout", "ticket-api")["spec"]["template"]["spec"]["containers"][0]
    container["env"] = [
        {"name": "RELEASE", "value": release},
        {"name": "INJECT_ERROR", "value": str(inject).lower()},
        {"name": "WORKER_URL", "value": "http://notification-worker:8000"},
    ]
    patch = {"spec": {"template": {"spec": {"containers": [container]}}}}
    print(
        kube(
            "-n",
            "delivery-lab",
            "patch",
            "rollout",
            "ticket-api",
            "--type=merge",
            "-p",
            json.dumps(patch),
        ),
        flush=True,
    )


def wait_release(release, expect_abort, output, timeout=360):
    deadline = time.monotonic() + timeout
    seen_weights = set()
    snapshots = []
    previous = None
    while time.monotonic() < deadline:
        rollout = object_get("rollout", "ticket-api")
        status = rollout.get("status", {})
        ingresses = json.loads(kube("-n", "delivery-lab", "get", "ingress", "-o", "json"))
        canary = next(
            i
            for i in ingresses["items"]
            if i["metadata"].get("annotations", {}).get("nginx.ingress.kubernetes.io/canary")
            == "true"
        )
        weight = int(
            canary.get("metadata", {})
            .get("annotations", {})
            .get("nginx.ingress.kubernetes.io/canary-weight", "0")
        )
        sample = {
            "at": datetime.now(UTC).isoformat(),
            "release": release,
            "phase": status.get("phase"),
            "step": status.get("currentStepIndex"),
            "weight": weight,
            "abort": status.get("abort", False),
            "stable_hash": status.get("stableRS"),
            "candidate_hash": status.get("currentPodHash"),
        }
        snapshots.append(sample)
        seen_weights.add(weight)
        summary = (sample["phase"], sample["step"], weight, sample["abort"])
        if summary != previous:
            print(
                f"{sample['at'][11:19]} {release:12} {str(sample['phase']):12} "
                f"step={str(sample['step']):2} traffic={weight:3}% "
                f"abort={sample['abort']} stable={sample['stable_hash']}",
                flush=True,
            )
            previous = summary
        current = str(status.get("observedGeneration")) == str(rollout["metadata"]["generation"])
        if current and expect_abort and status.get("abort") and weight == 0:
            assert status.get("stableRS") != status.get("currentPodHash")
            assert 10 in seen_weights, "Bad candidate never received 10% traffic"
            break
        if current and not expect_abort and status.get("phase") == "Healthy":
            assert {10, 50, 100}.issubset(seen_weights), f"Missing stages: {seen_weights}"
            assert status.get("stableRS") == status.get("currentPodHash")
            break
        time.sleep(2)
    else:
        raise TimeoutError(f"{release} rollout did not reach expected state")
    (output / f"{release}-timeline.json").write_text(json.dumps(snapshots, indent=2))
    (output / f"{release}-rollout.json").write_text(json.dumps(rollout, indent=2))
    analyses = json.loads(kube("-n", "delivery-lab", "get", "analysisrun", "-o", "json"))
    candidates = [
        a
        for a in analyses["items"]
        if any(arg.get("value") == status["currentPodHash"] for arg in a["spec"].get("args", []))
    ]
    (output / f"{release}-analysis.json").write_text(json.dumps(candidates, indent=2))
    phases = [a.get("status", {}).get("phase") for a in candidates]
    if expect_abort:
        assert "Failed" in phases, phases
        failures = [
            m
            for a in candidates
            for m in a.get("status", {}).get("metricResults", [])
            if m.get("name") == "error-rate" and m.get("phase") == "Failed"
        ]
        assert failures, "Expected failure was not caused by candidate error rate"
    else:
        assert len(candidates) == 2 and all(p == "Successful" for p in phases), phases
    return status


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, default=ROOT / "artifacts/demo")
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=True)
    # Distinct release IDs permit repeating the demo without reusing old analyses.
    suffix = datetime.now(UTC).strftime("%H%M%S")
    good, bad = "good-" + suffix, "bad-" + suffix
    print("GOOD RELEASE: real ingress 10% -> analysis -> 50% -> analysis -> 100%", flush=True)
    patch_release(good, False)
    stable = wait_release(good, False, args.output)
    print("GOOD RELEASE PROMOTED", flush=True)
    print("BAD RELEASE: inject HTTP 500; expect analysis failure and automatic abort", flush=True)
    patch_release(bad, True)
    aborted = wait_release(bad, True, args.output)
    assert aborted["stableRS"] == stable["stableRS"]
    time.sleep(5)  # Let ingress reload its zero-weight route.
    releases = []
    for _ in range(30):
        with urllib.request.urlopen("http://127.0.0.1:8088/api/tickets", timeout=5) as response:
            assert response.status == 200
            releases.append(json.load(response)["release"])
    assert set(releases) == {good}, releases
    print(
        "AUTOMATIC ROLLBACK VERIFIED: canary weight 0; 30/30 requests served by good release",
        flush=True,
    )
    deadline = time.monotonic() + 45
    while time.monotonic() < deadline:
        with urllib.request.urlopen("http://127.0.0.1:9098/api/v1/alerts", timeout=5) as response:
            alerts = json.load(response)["data"]["alerts"]
        if any(
            alert["labels"]["alertname"] == "CanaryDegraded" and alert["state"] == "firing"
            for alert in alerts
        ):
            break
        time.sleep(2)
    else:
        raise AssertionError("CanaryDegraded alert did not fire after automatic abort")
    (args.output / "alerts.json").write_text(json.dumps(alerts, indent=2))
    print("PROMETHEUS ALERT VERIFIED: CanaryDegraded is firing", flush=True)
    logs = kube(
        "-n",
        "argo-rollouts",
        "logs",
        "-l",
        "app.kubernetes.io/name=argo-rollouts",
        "--since=15m",
        "--prefix=true",
        "--tail=-1",
    )
    (args.output / "controller.log").write_text(logs)
    (args.output / "events.txt").write_text(
        kube("-n", "delivery-lab", "get", "events", "--sort-by=.lastTimestamp")
    )
    report = {
        "at": datetime.now(UTC).isoformat(),
        "good_release": good,
        "bad_release": bad,
        "good_analysis_runs": 2,
        "automatic_abort": True,
        "canary_weight_after_abort": 0,
        "recovery_requests": 30,
        "recovery_successes": 30,
        "stable_hash": stable["stableRS"],
        "bad_hash": aborted["currentPodHash"],
        "rollback_alert": "firing",
    }
    (args.output / "summary.json").write_text(json.dumps(report, indent=2))
    print(json.dumps(report), flush=True)


if __name__ == "__main__":
    lock = ROOT / "artifacts/demo.lock"
    lock.parent.mkdir(exist_ok=True)
    with lock.open("x"):
        pass
    try:
        main()
    except Exception as exc:
        print(f"DEMO FAILED: {exc}", file=sys.stderr)
        raise
    finally:
        lock.unlink(missing_ok=True)
