"""FastAPI application entry point."""

import uuid
from fastapi import FastAPI
from fastapi.responses import JSONResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles

from app.config import (
    MAX_FONT_UPLOAD_BYTES,
    MAX_STORAGE_BYTES,
    MAX_UPLOAD_BYTES,
    RATE_LIMIT_EDIT_PER_WINDOW,
    RATE_LIMIT_EXPORT_PER_WINDOW,
    RATE_LIMIT_UPLOAD_PER_WINDOW,
    RATE_LIMIT_WINDOW_SEC,
    STATIC_DIR,
    SESSION_COOKIE_NAME,
    ensure_directories,
)
from app.routes import auth, edit_subtitles, export, jobs, media, playback, upload
from app.services.cleanup import cleanup_storage
from app.services.auth import get_auth_context, init_auth_db
from app.services.jobs import start_workers
from app.services.rate_limit import check_rate_limit

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


@app.middleware("http")
async def rate_limit_middleware(request, call_next):
    if request.method == "POST":
        path = request.url.path
        client = request.client.host if request.client else "unknown"
        if path == "/upload":
            length = request.headers.get("content-length")
            if length and length.isdigit() and int(length) > MAX_UPLOAD_BYTES:
                return JSONResponse(status_code=413, content={"detail": "Upload too large"})
            allowed, retry_after = check_rate_limit(
                f"upload:{client}",
                RATE_LIMIT_UPLOAD_PER_WINDOW,
                RATE_LIMIT_WINDOW_SEC,
            )
        elif path.endswith("/font-upload"):
            length = request.headers.get("content-length")
            if length and length.isdigit() and int(length) > MAX_FONT_UPLOAD_BYTES:
                return JSONResponse(status_code=413, content={"detail": "Font upload too large"})
            allowed, retry_after = check_rate_limit(
                f"font:{client}",
                RATE_LIMIT_EDIT_PER_WINDOW,
                RATE_LIMIT_WINDOW_SEC,
            )
        elif path.startswith("/export/"):
            allowed, retry_after = check_rate_limit(
                f"export:{client}",
                RATE_LIMIT_EXPORT_PER_WINDOW,
                RATE_LIMIT_WINDOW_SEC,
            )
        elif path.startswith("/edit/"):
            allowed, retry_after = check_rate_limit(
                f"edit:{client}",
                RATE_LIMIT_EDIT_PER_WINDOW,
                RATE_LIMIT_WINDOW_SEC,
            )
        else:
            allowed = True
            retry_after = 0
        if not allowed:
            response = JSONResponse(status_code=429, content={"detail": "Too many requests. Try again shortly."})
            response.headers["Retry-After"] = str(retry_after)
            return response
    return await call_next(request)


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
