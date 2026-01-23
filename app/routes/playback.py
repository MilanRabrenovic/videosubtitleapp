"""Playback transcript endpoints."""

from typing import Any

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import RedirectResponse
from fastapi.templating import Jinja2Templates

from app.config import TEMPLATES_DIR
from app.services.cleanup import touch_job
from app.services.jobs import load_job, touch_job_access, update_job
from app.services.subtitles import load_subtitle_job, load_transcript_words

router = APIRouter()
templates = Jinja2Templates(directory=str(TEMPLATES_DIR))


def _require_user(request: Request):
    user = getattr(request.state, "user", None)
    if not user:
        return None
    return user


def _ensure_owner(job_id: str, user_id: int) -> bool:
    job_record = load_job(job_id)
    if not job_record:
        raise HTTPException(status_code=404, detail="Project not found")
    if job_record.get("owner_user_id") is None:
        update_job(job_id, {"owner_user_id": int(user_id)})
        job_record["owner_user_id"] = int(user_id)
    return job_record.get("owner_user_id") == int(user_id)


@router.get("/playback/{job_id}")
def playback_view(request: Request, job_id: str) -> Any:
    """Render a playback view with word-level transcript highlighting."""
    user = _require_user(request)
    if not user:
        return RedirectResponse(url="/login", status_code=303)
    if not _ensure_owner(job_id, user["id"]):
        raise HTTPException(status_code=403, detail="Access denied")
    job_data = load_subtitle_job(job_id)
    if not job_data:
        raise HTTPException(status_code=404, detail="Subtitle job not found")
    touch_job(job_id)
    touch_job_access(job_id)

    words = load_transcript_words(job_id)
    if not words:
        raise HTTPException(status_code=404, detail="Transcript words not found")

    return templates.TemplateResponse(
        "playback.html",
        {
            "request": request,
            "job": job_data,
            "words": words,
        },
    )
