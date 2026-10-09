import asyncio
import json
from collections import deque
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException
from prometheus_client import Counter, Gauge
from pydantic import BaseModel, Field

from services.common import instrument


class Event(BaseModel):
    id: str = Field(min_length=1, max_length=80)
    type: str = Field(pattern="^ticket.created$")
    title: str = Field(min_length=3, max_length=120)


def create_app():
    queue = asyncio.Queue(maxsize=1000)
    completed = deque(maxlen=1000)
    accepted = set()

    @asynccontextmanager
    async def lifespan(app):
        async def consume():
            while True:
                event = await queue.get()
                completed.append({**event, "status": "delivered", "channel": "local-log"})
                processed.inc()
                depth.set(queue.qsize())
                print(
                    json.dumps(
                        {
                            "event": "notification.delivered",
                            "ticket_id": event["id"],
                            "channel": "local-log",
                        }
                    ),
                    flush=True,
                )
                queue.task_done()

        task = asyncio.create_task(consume())
        yield
        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            pass

    app = FastAPI(title="Notification worker", lifespan=lifespan)
    registry = instrument(app, "notification-worker")
    processed = Counter("lab_notifications_total", "Delivered notifications", registry=registry)
    depth = Gauge("lab_notification_queue_depth", "Queued notifications", registry=registry)

    @app.post("/events", status_code=202)
    async def enqueue(event: Event):
        if event.id in accepted:
            return {"id": event.id, "status": "duplicate"}
        if len(accepted) >= 1000 or queue.full():
            raise HTTPException(503, "Local demo capacity reached; restart worker")
        queue.put_nowait(event.model_dump())
        accepted.add(event.id)
        depth.set(queue.qsize())
        return {"id": event.id, "status": "accepted"}

    @app.get("/notifications")
    def notifications():
        return {"notifications": list(completed)}

    return app


app = create_app()
