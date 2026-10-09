import asyncio
import json
import time

import httpx
import pytest
from fastapi.testclient import TestClient

from services.notification_worker.app import Event
from services.notification_worker.app import create_app as worker_app
from services.ticket_api.app import TicketInput
from services.ticket_api.app import create_app as api_app
from services.web_frontend.app import create_app as web_app


@pytest.fixture
def api():
    async def notify(event):
        assert Event(**event).type == "ticket.created"

    return TestClient(api_app(notify))


@pytest.mark.parametrize(
    "factory,name",
    [(api_app, "ticket-api"), (worker_app, "notification-worker"), (web_app, "web-frontend")],
)
def test_health_readiness_metrics_contract(factory, name):
    with TestClient(factory()) as client:
        assert client.get("/health").json()["service"] == name
        assert client.get("/ready").json() == {"status": "ready", "service": name}
        assert client.get("/metrics").status_code == 200


def test_ticket_model_validation():
    assert TicketInput(title="Example").priority == "normal"
    with pytest.raises(ValueError):
        TicketInput(title="x")
    with pytest.raises(ValueError):
        TicketInput(title="Example", priority="urgent")


def test_ticket_create_and_list_contract(api):
    response = api.post("/api/tickets", json={"title": "Synthetic ticket", "priority": "high"})
    assert response.status_code == 201
    ticket = response.json()
    assert set(ticket) == {"id", "title", "priority", "status"}
    assert ticket["status"] == "open"
    assert api.get("/api/tickets").json()["tickets"] == [ticket]
    assert api.post("/api/tickets", json={"title": "x"}).status_code == 422


def test_injected_fault_keeps_probes_healthy(api, monkeypatch):
    monkeypatch.setenv("INJECT_ERROR", "true")
    assert api.get("/api/tickets").status_code == 500
    assert api.post("/api/tickets", json={"title": "Example"}).status_code == 500
    assert api.get("/health").status_code == 200
    assert api.get("/ready").status_code == 200


def test_downstream_failure_does_not_create_ticket():
    async def fail(event):
        raise httpx.ConnectError("offline")

    client = TestClient(api_app(fail))
    assert client.post("/api/tickets", json={"title": "Example"}).status_code == 503
    assert client.get("/api/tickets").json()["tickets"] == []


def test_metrics_and_json_logs(api, capsys):
    response = api.get("/api/tickets")
    metrics = api.get("/metrics").text
    assert 'service="ticket-api"' in metrics
    assert 'route="/api/tickets"' in metrics
    assert "lab_http_request_duration_seconds_bucket" in metrics
    entry = json.loads(capsys.readouterr().out.strip())
    assert entry["status"] == 200
    assert entry["request_id"] == response.headers["X-Request-ID"]


def test_worker_validation():
    with pytest.raises(ValueError):
        Event(id="1", type="unknown", title="Example")


def test_worker_contract_and_idempotency():
    with TestClient(worker_app()) as client:
        event = {"id": "synthetic-1", "type": "ticket.created", "title": "Example"}
        assert client.post("/events", json=event).json()["status"] == "accepted"
        assert client.post("/events", json=event).json()["status"] == "duplicate"
        for _ in range(30):
            items = client.get("/notifications").json()["notifications"]
            if items:
                break
            time.sleep(0.01)
        assert items == [{**event, "status": "delivered", "channel": "local-log"}]
        assert "lab_notifications_total 1.0" in client.get("/metrics").text
        assert client.post("/events", json={}).status_code == 422


def test_api_worker_cross_service_contract():
    with TestClient(worker_app()) as worker:

        async def notify(event):
            result = await asyncio.to_thread(worker.post, "/events", json=event)
            assert result.status_code == 202

        with TestClient(api_app(notify)) as api:
            ticket = api.post("/api/tickets", json={"title": "Contract integration"}).json()
            for _ in range(30):
                items = worker.get("/notifications").json()["notifications"]
                if items:
                    break
                time.sleep(0.01)
            assert items[0]["id"] == ticket["id"]


def test_frontend_html_contract():
    with TestClient(web_app()) as client:
        response = client.get("/")
        assert response.status_code == 200
        assert "text/html" in response.headers["content-type"]
        assert 'id="ticket-form"' in response.text
        assert "fetch('/api/tickets'" in response.text
        assert "textContent=t.title" in response.text
        assert "lab_http_requests_total" in client.get("/metrics").text
