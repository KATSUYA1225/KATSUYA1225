from fastapi import FastAPI
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from pathlib import Path

app = FastAPI(docs_url=None, redoc_url=None)
app.mount("/static", StaticFiles(directory=str(Path(__file__).parent / "static")), name="static")

@app.get("/", response_class=HTMLResponse)
async def root() -> HTMLResponse:
    html = (Path(__file__).parent / "static" / "landing2.html").read_text(encoding="utf-8")
    return HTMLResponse(content=html)

@app.get("/lp", response_class=HTMLResponse)
async def landing_v1() -> HTMLResponse:
    html = (Path(__file__).parent / "static" / "landing.html").read_text(encoding="utf-8")
    return HTMLResponse(content=html)

@app.get("/register", response_class=HTMLResponse)
async def register_page() -> HTMLResponse:
    html = (Path(__file__).parent / "static" / "register.html").read_text(encoding="utf-8")
    return HTMLResponse(content=html)

@app.get("/early", response_class=RedirectResponse)
async def early_redirect() -> RedirectResponse:
    return RedirectResponse(url="/register", status_code=302)

@app.get("/app", response_class=HTMLResponse)
async def app_ui() -> HTMLResponse:
    html = (Path(__file__).parent / "static" / "index.html").read_text(encoding="utf-8")
    return HTMLResponse(content=html)

@app.get("/skill", response_class=HTMLResponse)
async def skill_page() -> HTMLResponse:
    html = (Path(__file__).parent / "static" / "skill.html").read_text(encoding="utf-8")
    return HTMLResponse(content=html)
