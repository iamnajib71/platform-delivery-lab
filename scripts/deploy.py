"""Use exactly the checked-in manifests on Windows and Actions."""

import argparse
import json
import subprocess
import time
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]


def run(*args, stdin=None):
    return subprocess.check_output(args, input=stdin, text=True)


def kube(*args, stdin=None):
    return run("kubectl", "--kubeconfig", str(ROOT / ".kube/config"), *args, stdin=stdin)


def wait_healthy(timeout=300):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        rollout = json.loads(
            kube("-n", "delivery-lab", "get", "rollout", "ticket-api", "-o", "json")
        )
        status = rollout.get("status", {})
        if (
            str(status.get("observedGeneration")) == str(rollout["metadata"]["generation"])
            and status.get("phase") == "Healthy"
        ):
            print("ticket-api Healthy")
            return
        if status.get("phase") == "Degraded":
            raise RuntimeError(json.dumps(status))
        time.sleep(3)
    raise TimeoutError("ticket-api did not become Healthy")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--tag", default="local")
    parser.add_argument("--load", action="store_true")
    args = parser.parse_args()
    if args.load:
        for service in ("ticket-api", "notification-worker", "web-frontend"):
            image = f"ghcr.io/iamnajib71/platform-delivery-lab/{service}:{args.tag}"
            print(run("kind", "load", "docker-image", image, "--name", "platform-delivery-lab"))
    for filename in ("namespace", "services", "analysis", "deployments", "rollout", "ingress"):
        documents = list(yaml.safe_load_all((ROOT / f"k8s/{filename}.yaml").read_text()))
        for document in documents:
            spec = document.get("spec", {}).get("template", {}).get("spec", {})
            for container in spec.get("containers", []):
                container["image"] = container["image"].replace(":local", ":" + args.tag)
        print(kube("apply", "-f", "-", stdin=yaml.safe_dump_all(documents)))
    for name in ("notification-worker", "web-frontend"):
        print(
            kube("-n", "delivery-lab", "rollout", "status", "deployment/" + name, "--timeout=180s")
        )
    wait_healthy()
    config = kube(
        "-n",
        "delivery-lab",
        "create",
        "configmap",
        "load-script",
        "--from-file=" + str(ROOT / "scripts/load.py"),
        "--dry-run=client",
        "-o",
        "yaml",
    )
    print(kube("apply", "-f", "-", stdin=config))
    load = {
        "apiVersion": "apps/v1",
        "kind": "Deployment",
        "metadata": {"name": "load-generator", "namespace": "delivery-lab"},
        "spec": {
            "replicas": 1,
            "selector": {"matchLabels": {"app": "load-generator"}},
            "template": {
                "metadata": {"labels": {"app": "load-generator"}},
                "spec": {
                    "securityContext": {"runAsNonRoot": True, "runAsUser": 10001},
                    "containers": [
                        {
                            "name": "load",
                            "image": "python:3.12-slim-bookworm",
                            "command": ["python", "/scripts/load.py"],
                            "resources": {
                                "requests": {"cpu": "50m", "memory": "32Mi"},
                                "limits": {"cpu": "500m", "memory": "96Mi"},
                            },
                            "volumeMounts": [{"name": "script", "mountPath": "/scripts"}],
                        }
                    ],
                    "volumes": [{"name": "script", "configMap": {"name": "load-script"}}],
                },
            },
        },
    }
    print(kube("apply", "-f", "-", stdin=yaml.safe_dump(load)))
    print(
        kube(
            "-n", "delivery-lab", "rollout", "status", "deployment/load-generator", "--timeout=180s"
        )
    )


if __name__ == "__main__":
    main()
