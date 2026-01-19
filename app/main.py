"""FastAPI application entry point."""

from fastapi import FastAPI
from fastapi.responses import RedirectResponse
from fastapi.staticfiles import StaticFiles

from app.config import STATIC_DIR, ensure_directories
from app.routes import edit_subtitles, export, upload

app = FastAPI(title="Subtitle App", version="0.1.0")

# Serve static assets (JS).
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")

# Register routes.
app.include_router(upload.router)
app.include_router(edit_subtitles.router)
app.include_router(export.router)


@app.on_event("startup")
def startup() -> None:
    """Ensure filesystem layout is ready at boot."""
    ensure_directories()


@app.get("/")
def index() -> RedirectResponse:
    """Redirect to the upload page."""
    return RedirectResponse(url="/upload", status_code=303)
