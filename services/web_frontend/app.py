from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import HTMLResponse

from services.common import instrument


def create_app():
    app = FastAPI(title="Delivery Lab console")
    instrument(app, "web-frontend")

    @app.get("/", response_class=HTMLResponse)
    def index():
        return Path(__file__).with_name("index.html").read_text(encoding="utf-8")

    return app


app = create_app()
