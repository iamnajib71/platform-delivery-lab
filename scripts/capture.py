"""Take actual application/dashboard screenshots and exercise the browser form."""

import json
from pathlib import Path

from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[1]
output = ROOT / "docs/img"
output.mkdir(parents=True, exist_ok=True)
with sync_playwright() as playwright:
    browser = playwright.chromium.launch()
    page = browser.new_page(viewport={"width": 1440, "height": 1080}, device_scale_factor=1)
    errors = []
    page.on("pageerror", lambda error: errors.append(str(error)))
    page.goto("http://localhost:8088", wait_until="networkidle")
    page.get_by_label("Ticket title").fill("Synthetic workstation access request")
    page.get_by_role("button", name="Create ticket & notify").click()
    page.get_by_role("status").filter(has_text="Ticket created.").wait_for()
    assert not errors, errors
    page.screenshot(path=str(output / "console.png"), full_page=True)
    page.goto(
        "http://localhost:3008/d/lab/platform-delivery-lab?from=now-5m&to=now&kiosk",
        wait_until="networkidle",
    )
    page.get_by_text("Request rate by release", exact=True).wait_for(timeout=60000)
    page.wait_for_timeout(8000)
    page.screenshot(path=str(output / "grafana.png"), full_page=True)
    browser.close()
print(json.dumps({"browser_form": "passed", "page_errors": errors, "screenshots": 2}))
