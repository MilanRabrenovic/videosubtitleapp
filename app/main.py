"""FastAPI application entry point."""

import uuid
from fastapi import FastAPI
from fastapi.responses import RedirectResponse
from fastapi.staticfiles import StaticFiles

from app.config import MAX_STORAGE_BYTES, STATIC_DIR, SESSION_COOKIE_NAME, ensure_directories
from app.routes import auth, edit_subtitles, export, jobs, media, playback, upload
from app.services.cleanup import cleanup_storage
from app.services.auth import get_auth_context, init_auth_db
from app.services.jobs import start_workers

app = FastAPI(title="Subtitle App", version="0.1.0")

# Serve static assets (JS).
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")

# Register routes.
app.include_router(auth.router)
app.include_router(upload.router)
app.include_router(edit_subtitles.router)
app.include_router(export.router)
app.include_router(playback.router)
app.include_router(jobs.router)
app.include_router(media.router)

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


@app.middleware("http")
async def auth_middleware(request, call_next):
    auth = get_auth_context(request)
    request.state.user = auth.user
    response = await call_next(request)
    return response


@app.on_event("startup")
def startup() -> None:
    """Ensure filesystem layout is ready at boot."""
    ensure_directories()
    cleanup_storage(MAX_STORAGE_BYTES)
    init_auth_db()
    start_workers()


@app.get("/")
def index() -> RedirectResponse:
    """Redirect to the upload page."""
    return RedirectResponse(url="/upload", status_code=303)
