"""Upload endpoints for new video jobs."""

import logging
import uuid
from pathlib import Path
from typing import Any, Dict

from fastapi import APIRouter, File, Form, HTTPException, Request, UploadFile
from fastapi.responses import RedirectResponse
from fastapi.templating import Jinja2Templates

from app.config import OUTPUTS_DIR, TEMPLATES_DIR, UPLOADS_DIR
from app.services.subtitles import (
    generate_karaoke_ass,
    save_subtitle_job,
    save_transcript_words,
    subtitles_to_srt,
    whisper_segments_to_subtitles,
)
from app.services.transcription import transcribe_video
from app.services.video import burn_in_ass

router = APIRouter()
templates = Jinja2Templates(directory=str(TEMPLATES_DIR))
logger = logging.getLogger(__name__)


@router.get("/upload")
def upload_form(request: Request) -> Any:
    """Render the upload form."""
    return templates.TemplateResponse("upload.html", {"request": request})


@router.post("/upload")
def handle_upload(request: Request, video: UploadFile = File(...), title: str = Form("")) -> Any:
    """Accept an uploaded video and create a subtitle job."""
    job_id = uuid.uuid4().hex
    safe_name = f"{job_id}_{Path(video.filename).name}"
    upload_path = UPLOADS_DIR / safe_name

    with upload_path.open("wb") as handle:
        handle.write(video.file.read())

    try:
        segments, words = transcribe_video(upload_path)
        subtitles = whisper_segments_to_subtitles(segments)
    except Exception as exc:  # noqa: BLE001 - keep errors simple for now
        logger.exception("Transcription failed for %s", upload_path)
        raise HTTPException(status_code=500, detail="Transcription failed") from exc

    job_data: Dict[str, Any] = {
        "job_id": job_id,
        "title": title.strip() or video.filename,
        "video_filename": safe_name,
        "subtitles": subtitles,
    }

    save_subtitle_job(job_id, job_data)
    save_transcript_words(job_id, words)
    srt_path = OUTPUTS_DIR / f"{job_id}.srt"
    srt_path.write_text(subtitles_to_srt(subtitles), encoding="utf-8")
    preview_path = OUTPUTS_DIR / f"{job_id}_preview.mp4"
    preview_ass_path = OUTPUTS_DIR / f"{job_id}_preview.ass"
    try:
        generate_karaoke_ass(words, preview_ass_path)
        burn_in_ass(upload_path, preview_ass_path, preview_path)
    except RuntimeError as exc:
        logger.exception("Preview burn-in failed for %s", preview_path)
        raise HTTPException(status_code=500, detail="Preview generation failed") from exc

    return RedirectResponse(url=f"/edit/{job_id}", status_code=303)
