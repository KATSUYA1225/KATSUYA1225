from fastapi import FastAPI
from fastapi.responses import HTMLResponse
from pathlib import Path

app = FastAPI(docs_url=None, redoc_url=None)

@app.get("/", response_class=HTMLResponse)
async def root() -> HTMLResponse:
    html = (Path(__file__).parent / "static" / "landing2.html").read_text(encoding="utf-8")
    return HTMLResponse(content=html)

@app.get("/app", response_class=HTMLResponse)
async def app_ui() -> HTMLResponse:
    html = (Path(__file__).parent / "static" / "index.html").read_text(encoding="utf-8")
    return HTMLResponse(content=html)
