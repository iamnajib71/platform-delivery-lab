"""Sustained synthetic ingress traffic (fresh connections for canary distribution)."""

import concurrent.futures
import os
import time
import urllib.error
import urllib.request

url = os.getenv("LOAD_URL", "http://ingress-ingress-nginx-controller.ingress-nginx/api/tickets")


def request(_):
    try:
        with urllib.request.urlopen(url, timeout=5) as response:
            response.read()
    except (urllib.error.URLError, TimeoutError):
        pass  # Injected HTTP 500 is expected; Prometheus records it at the API.


with concurrent.futures.ThreadPoolExecutor(max_workers=8) as pool:
    while True:
        started = time.monotonic()
        list(pool.map(request, range(30)))
        time.sleep(max(0, 1 - (time.monotonic() - started)))
