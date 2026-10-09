"""Rebuild the provisioned dashboard from reviewed PromQL queries."""

import json
from pathlib import Path

panels = []
queries = [
    (
        "Request rate by release",
        'sum by (release) (rate(lab_http_requests_total{service="ticket-api"}[1m]))',
        "reqps",
    ),
    (
        "HTTP 5xx rate by release",
        '(sum by (release) (rate(lab_http_requests_total{service="ticket-api",'
        'status=~"5.."}[1m])) or on(release) '
        '(0 * sum by (release) (rate(lab_http_requests_total{service="ticket-api"}[1m])))) '
        '/ sum by (release) (rate(lab_http_requests_total{service="ticket-api"}[1m]))',
        "percentunit",
    ),
    (
        "p95 request latency",
        "histogram_quantile(0.95, sum by (le, release) "
        '(rate(lab_http_request_duration_seconds_bucket{service="ticket-api"}[1m])))',
        "s",
    ),
    ("Rollout status", 'rollout_info{name="ticket-api",namespace="delivery-lab"}', "short"),
    ("Delivered notifications", "lab_notifications_total", "short"),
    ("Service scrape health", 'up{job="lab-services"}', "short"),
]
for index, (title, expression, unit) in enumerate(queries):
    fields = {"unit": unit}
    if unit == "percentunit":
        fields.update({"min": 0, "max": 1})
    panels.append(
        {
            "id": index + 1,
            "title": title,
            "type": "timeseries",
            "gridPos": {"h": 8, "w": 12, "x": (index % 2) * 12, "y": (index // 2) * 8},
            "datasource": {"type": "prometheus", "uid": "prometheus"},
            "targets": [
                {"refId": "A", "expr": expression, "legendFormat": "{{phase}} {{release}} {{pod}}"}
            ],
            "fieldConfig": {"defaults": fields, "overrides": []},
            "options": {"legend": {"displayMode": "list", "placement": "bottom"}},
        }
    )
dashboard = {
    "uid": "lab",
    "title": "Platform Delivery Lab",
    "schemaVersion": 39,
    "version": 1,
    "refresh": "5s",
    "tags": ["canary", "local", "platform"],
    "time": {"from": "now-15m", "to": "now"},
    "timezone": "browser",
    "panels": panels,
}
path = Path(__file__).resolve().parents[1] / "ops/dashboard.json"
path.parent.mkdir(exist_ok=True)
path.write_text(json.dumps(dashboard, indent=2) + "\n")
