"""Subtitle editing endpoints."""

import json
import logging
from typing import Any

from fastapi import APIRouter, Form, HTTPException, Request
from fastapi.templating import Jinja2Templates

from app.config import OUTPUTS_DIR, TEMPLATES_DIR, UPLOADS_DIR
from app.services.subtitles import (
    generate_karaoke_ass,
    load_subtitle_job,
    load_transcript_words,
    save_subtitle_job,
    subtitles_to_srt,
)
from app.services.video import burn_in_ass, burn_in_subtitles

router = APIRouter()
templates = Jinja2Templates(directory=str(TEMPLATES_DIR))
logger = logging.getLogger(__name__)


@router.get("/edit/{job_id}")
def edit_page(request: Request, job_id: str) -> Any:
    """Render the subtitle editing UI."""
    job_data = load_subtitle_job(job_id)
    if not job_data:
        raise HTTPException(status_code=404, detail="Subtitle job not found")

    preview_path = OUTPUTS_DIR / f"{job_id}_preview.mp4"
    return templates.TemplateResponse(
        "edit.html",
        {
            "request": request,
            "job": job_data,
            "preview_available": preview_path.exists(),
        },
    )


@router.post("/edit/{job_id}")
def save_edits(request: Request, job_id: str, subtitles_json: str = Form(...)) -> Any:
    """Persist edited subtitles without reprocessing the video."""
    job_data = load_subtitle_job(job_id)
    if not job_data:
        raise HTTPException(status_code=404, detail="Subtitle job not found")

    try:
        subtitles = json.loads(subtitles_json)
    except json.JSONDecodeError as exc:
        raise HTTPException(status_code=400, detail="Invalid subtitle payload") from exc

    job_data["subtitles"] = subtitles
    save_subtitle_job(job_id, job_data)
    srt_path = OUTPUTS_DIR / f"{job_id}.srt"
    srt_path.write_text(subtitles_to_srt(subtitles), encoding="utf-8")
    preview_path = OUTPUTS_DIR / f"{job_id}_preview.mp4"
    preview_ass_path = OUTPUTS_DIR / f"{job_id}_preview.ass"
    video_path = UPLOADS_DIR / job_data.get("video_filename", "")
    words = load_transcript_words(job_id)
    if video_path.exists():
        try:
            if words:
                generate_karaoke_ass(words, preview_ass_path)
                burn_in_ass(video_path, preview_ass_path, preview_path)
            else:
                burn_in_subtitles(video_path, srt_path, preview_path)
        except RuntimeError:
            logger.exception("Preview burn-in failed for %s", preview_path)

    return templates.TemplateResponse(
        "edit.html",
        {
            "request": request,
            "job": job_data,
            "saved": True,
            "preview_available": preview_path.exists(),
        },
    )
