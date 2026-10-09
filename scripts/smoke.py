import json
import sys
import time
import urllib.request

base = sys.argv[1] if len(sys.argv) > 1 else "http://localhost:8088"


def get(path):
    with urllib.request.urlopen(base + path, timeout=10) as response:
        return json.load(response)


with urllib.request.urlopen(base + "/", timeout=10) as response:
    assert b"Ship. Measure. Recover." in response.read()
assert "tickets" in get("/api/tickets")
request = urllib.request.Request(
    base + "/api/tickets",
    method="POST",
    data=json.dumps({"title": "Synthetic smoke ticket", "priority": "normal"}).encode(),
    headers={"Content-Type": "application/json"},
)
with urllib.request.urlopen(request, timeout=10) as response:
    assert response.status == 201
    ticket = json.load(response)
for _ in range(30):
    events = get("/notifications")["notifications"]
    if any(event["id"] == ticket["id"] and event["status"] == "delivered" for event in events):
        break
    time.sleep(1)
else:
    raise AssertionError("Worker did not deliver the ticket notification")
print(
    json.dumps(
        {
            "smoke": "passed",
            "frontend": 200,
            "ticket_create": 201,
            "notification": "delivered",
            "ticket_id": ticket["id"],
        }
    )
)
