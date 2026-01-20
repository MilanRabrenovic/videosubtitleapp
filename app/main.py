"""FastAPI application entry point."""

from fastapi import FastAPI
from fastapi.responses import RedirectResponse
from fastapi.staticfiles import StaticFiles

from app.config import MAX_STORAGE_BYTES, OUTPUTS_DIR, STATIC_DIR, UPLOADS_DIR, ensure_directories
from app.routes import edit_subtitles, export, playback, upload
from app.services.cleanup import cleanup_storage

app = FastAPI(title="Subtitle App", version="0.1.0")

# Serve static assets (JS).
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")
app.mount("/uploads", StaticFiles(directory=UPLOADS_DIR), name="uploads")
app.mount("/outputs", StaticFiles(directory=OUTPUTS_DIR), name="outputs")

# Register routes.
app.include_router(upload.router)
app.include_router(edit_subtitles.router)
app.include_router(export.router)
app.include_router(playback.router)


@app.on_event("startup")
def startup() -> None:
    """Ensure filesystem layout is ready at boot."""
    ensure_directories()
    cleanup_storage(MAX_STORAGE_BYTES)


@app.get("/")
def index() -> RedirectResponse:
    """Redirect to the upload page."""
    return RedirectResponse(url="/upload", status_code=303)
