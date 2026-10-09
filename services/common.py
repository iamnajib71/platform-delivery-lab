"""Bounded metrics labels and JSON request logs shared by all three services."""

import json
import os
import time
import uuid

from fastapi import FastAPI, Request
from prometheus_client import CollectorRegistry, Counter, Histogram, generate_latest
from starlette.responses import Response


def instrument(app: FastAPI, service: str) -> CollectorRegistry:
    registry = CollectorRegistry()
    labels = ["service", "release", "route", "status"]
    requests = Counter("lab_http_requests_total", "HTTP requests", labels, registry=registry)
    latency = Histogram(
        "lab_http_request_duration_seconds",
        "Request duration",
        labels,
        buckets=(0.005, 0.01, 0.025, 0.05, 0.1, 0.3, 0.5, 1, 2),
        registry=registry,
    )
    release = os.getenv("RELEASE", "baseline")

    @app.middleware("http")
    async def observe(request: Request, call_next):
        started = time.perf_counter()
        request_id = str(uuid.uuid4())
        response = await call_next(request)
        elapsed = time.perf_counter() - started
        route = getattr(request.scope.get("route"), "path", "unmatched")
        if route not in ("/health", "/ready", "/metrics"):
            values = (service, release, route, str(response.status_code))
            requests.labels(*values).inc()
            latency.labels(*values).observe(elapsed)
            print(
                json.dumps(
                    {
                        "event": "request",
                        "service": service,
                        "release": release,
                        "request_id": request_id,
                        "method": request.method,
                        "route": route,
                        "status": response.status_code,
                        "duration_ms": round(elapsed * 1000, 3),
                    }
                ),
                flush=True,
            )
        response.headers["X-Request-ID"] = request_id
        response.headers["X-Release"] = release
        return response

    @app.get("/health")
    def health():
        return {"status": "ok", "service": service, "release": release}

    @app.get("/ready")
    def ready():
        return {"status": "ready", "service": service}

    @app.get("/metrics")
    def metrics():
        return Response(generate_latest(registry), media_type="text/plain; version=0.0.4")

    return registry
