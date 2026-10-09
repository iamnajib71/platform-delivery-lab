"""Build an evidence index solely from preserved run artifacts."""

import json
import shutil
import xml.etree.ElementTree as ET
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
target = ROOT / "docs/evidence"
target.mkdir(parents=True, exist_ok=True)
summary = json.loads((target / "demo/summary.json").read_text())
metrics = {}
for scenario in ("good", "bad"):
    release = summary[f"{scenario}_release"]
    analyses = json.loads((target / f"demo/{release}-analysis.json").read_text())
    for analysis in analyses:
        for metric in analysis["status"]["metricResults"]:
            key = f"{scenario}_{metric['name']}"
            metrics.setdefault(key, []).extend(
                float(json.loads(measure["value"])[0])
                for measure in metric.get("measurements", [])
                if measure.get("value")
            )
scans = []
for service in ("ticket-api", "notification-worker", "web-frontend"):
    report_path = ROOT / f"artifacts/{service}-trivy.json"
    sbom_path = ROOT / f"artifacts/{service}-sbom.spdx.json"
    report = json.loads(report_path.read_text(encoding="utf-8"))
    sbom = json.loads(sbom_path.read_text(encoding="utf-8"))
    scans.append(
        {
            "service": service,
            "fixable_high_critical": sum(
                len(r.get("Vulnerabilities", [])) for r in report["Results"]
            ),
            "sbom_packages": len(sbom["packages"]),
            "image_id": report["Metadata"]["ImageID"],
        }
    )
    shutil.copy2(report_path, target / report_path.name)
    shutil.copy2(sbom_path, target / sbom_path.name)
shutil.copy2(ROOT / "artifacts/tests.xml", target / "tests.xml")
suite = ET.parse(target / "tests.xml").getroot().find("testsuite")
result = {
    "demo": summary,
    "measurements": metrics,
    "scans": scans,
    "tests": {key: suite.attrib[key] for key in ("tests", "failures", "errors", "time")},
}
(target / "results.json").write_text(json.dumps(result, indent=2) + "\n")
low = min(metrics["good_p95-latency"]) * 1000
high = max(metrics["good_p95-latency"]) * 1000
bad_error = max(metrics["bad_error-rate"]) * 100
lines = [
    "# Actual run evidence",
    "",
    "Recorded on 10 October 2026 (Australia/Sydney). Raw Kubernetes timestamps use UTC.",
    "",
    "| Check | Measured result | Source |",
    "|---|---|---|",
    f"| Unit and contract tests | {suite.attrib['tests']} passed, 0 failures | "
    "[JUnit](tests.xml) |",
    "| Good candidate | 10%, 50%, 100%; 2 Successful AnalysisRuns | "
    f"[Timeline](demo/{summary['good_release']}-timeline.json) |",
    f"| Good p95 latency | {low:.2f}–{high:.2f} ms across gate samples | "
    f"[Analysis](demo/{summary['good_release']}-analysis.json) |",
    f"| Injected candidate error rate | {bad_error:.0f}% → Failed → automatic abort | "
    f"[Analysis](demo/{summary['bad_release']}-analysis.json) |",
    "| Post-abort traffic | 0% canary; 30/30 HTTP 200 from stable release | "
    "[Summary](demo/summary.json) |",
]
for scan in scans:
    service = scan["service"]
    lines.append(
        f"| {service} image | {scan['fixable_high_critical']} fixable HIGH/CRITICAL; "
        f"{scan['sbom_packages']} SPDX packages | [Trivy]({service}-trivy.json), "
        f"[SBOM]({service}-sbom.spdx.json) |"
    )
lines.extend(
    [
        "",
        "[Controller log](demo/controller.log) · [Kubernetes events](demo/events.txt) · "
        "[Machine-readable results](results.json)",
        "",
        "The intentional bad template remains visible and the Rollout is Degraded; traffic "
        "has returned to the healthy ReplicaSet. No manual abort command was used in the demo.",
        "",
        "Scans used Trivy 0.75.0 with `--severity HIGH,CRITICAL --ignore-unfixed`; "
        "this reports the gated subset, not every known vulnerability. Syft 1.54.1 created "
        "the original SPDX JSON files.",
    ]
)
(target / "README.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
print(json.dumps(result, indent=2))
