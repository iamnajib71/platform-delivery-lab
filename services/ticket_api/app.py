import os
import uuid
from collections import deque

import httpx
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field

from services.common import instrument


class TicketInput(BaseModel):
    title: str = Field(min_length=3, max_length=120)
    priority: str = Field(default="normal", pattern="^(low|normal|high)$")


def create_app(notify=None):
    app = FastAPI(title="Ticket API", version="1.0.0")
    instrument(app, "ticket-api")
    tickets = deque(maxlen=1000)

    async def send_notification(event):
        async with httpx.AsyncClient(timeout=3) as client:
            response = await client.post(
                os.getenv("WORKER_URL", "http://notification-worker:8000") + "/events",
                json=event,
            )
            response.raise_for_status()

    @app.get("/api/tickets")
    def list_tickets():
        if os.getenv("INJECT_ERROR", "false").lower() == "true":
            raise HTTPException(500, "Injected release fault")
        return {"tickets": list(tickets), "release": os.getenv("RELEASE", "baseline")}

    @app.post("/api/tickets", status_code=201)
    async def create_ticket(body: TicketInput):
        if os.getenv("INJECT_ERROR", "false").lower() == "true":
            raise HTTPException(500, "Injected release fault")
        ticket = {"id": str(uuid.uuid4()), **body.model_dump(), "status": "open"}
        try:
            await (notify or send_notification)(
                {"id": ticket["id"], "type": "ticket.created", "title": ticket["title"]}
            )
        except httpx.HTTPError as exc:
            raise HTTPException(503, "Notification service unavailable") from exc
        tickets.append(ticket)
        return ticket

    return app


app = create_app()
