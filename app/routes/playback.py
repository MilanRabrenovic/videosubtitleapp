"""Playback transcript endpoints."""

from typing import Any

from fastapi import APIRouter, HTTPException, Request
from fastapi.templating import Jinja2Templates

from app.config import TEMPLATES_DIR
from app.services.subtitles import load_subtitle_job, load_transcript_words

router = APIRouter()
templates = Jinja2Templates(directory=str(TEMPLATES_DIR))


@router.get("/playback/{job_id}")
def playback_view(request: Request, job_id: str) -> Any:
    """Render a playback view with word-level transcript highlighting."""
    job_data = load_subtitle_job(job_id)
    if not job_data:
        raise HTTPException(status_code=404, detail="Subtitle job not found")

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
