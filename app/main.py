"""FastAPI application entry point."""

import uuid
from fastapi import FastAPI
from fastapi.responses import RedirectResponse
from fastapi.staticfiles import StaticFiles

from app.config import MAX_STORAGE_BYTES, OUTPUTS_DIR, STATIC_DIR, UPLOADS_DIR, SESSION_COOKIE_NAME, ensure_directories
from app.routes import edit_subtitles, export, jobs, playback, upload
from app.services.cleanup import cleanup_storage
from app.services.jobs import start_workers

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
app.include_router(jobs.router)

@app.middleware("http")
async def session_middleware(request, call_next):
    session_id = request.cookies.get(SESSION_COOKIE_NAME)
    if not session_id:
        session_id = uuid.uuid4().hex
        request.state.session_id = session_id
        response = await call_next(request)
        response.set_cookie(
            SESSION_COOKIE_NAME,
            session_id,
            httponly=True,
            samesite="Lax",
        )
        return response
    request.state.session_id = session_id
    return await call_next(request)


@app.on_event("startup")
def startup() -> None:
    """Ensure filesystem layout is ready at boot."""
    ensure_directories()
    cleanup_storage(MAX_STORAGE_BYTES)
    start_workers()


@app.get("/")
def index() -> RedirectResponse:
    """Redirect to the upload page."""
    return RedirectResponse(url="/upload", status_code=303)
