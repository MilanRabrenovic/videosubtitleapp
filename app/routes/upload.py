"""Upload endpoints for new video jobs."""

import logging
import uuid
from pathlib import Path
from typing import Any, Dict

from fastapi import APIRouter, File, Form, HTTPException, Request, UploadFile
from fastapi.responses import RedirectResponse
from fastapi.templating import Jinja2Templates

from app.config import (
    ALLOWED_VIDEO_EXTENSIONS,
    MAX_STORAGE_BYTES,
    MAX_UPLOAD_BYTES,
    MAX_VIDEO_SECONDS,
    OUTPUTS_DIR,
    TEMPLATES_DIR,
    UPLOADS_DIR,
)
from app.services.cleanup import cleanup_storage, touch_job
from app.services.fonts import ensure_font_downloaded, font_dir_for_name
from app.services.subtitles import (
    build_karaoke_lines,
    default_style,
    generate_karaoke_ass,
    save_subtitle_job,
    save_transcript_words,
    split_subtitles_by_word_timings,
    split_subtitles_by_words,
    subtitles_to_srt,
    whisper_segments_to_subtitles,
)
from app.services.transcription import transcribe_video
from app.services.video import burn_in_ass, get_video_dimensions, validate_video_file

router = APIRouter()
templates = Jinja2Templates(directory=str(TEMPLATES_DIR))
logger = logging.getLogger(__name__)


@router.get("/upload")
def upload_form(request: Request) -> Any:
    """Render the upload form."""
    return templates.TemplateResponse("upload.html", {"request": request})


@router.post("/upload")
def handle_upload(
    request: Request,
    video: UploadFile = File(...),
    title: str = Form(""),
    language: str = Form(""),
) -> Any:
    """Accept an uploaded video and create a subtitle job."""
    job_id = uuid.uuid4().hex
    extension = Path(video.filename).suffix.lower()
    if extension not in ALLOWED_VIDEO_EXTENSIONS:
        raise HTTPException(status_code=400, detail="Unsupported video format")
    safe_name = f"{job_id}_{Path(video.filename).name}"
    upload_path = UPLOADS_DIR / safe_name

    with upload_path.open("wb") as handle:
        while True:
            chunk = video.file.read(1024 * 1024)
            if not chunk:
                break
            handle.write(chunk)
    cleanup_storage(MAX_STORAGE_BYTES)

    try:
        validate_video_file(upload_path, MAX_UPLOAD_BYTES, MAX_VIDEO_SECONDS)
    except ValueError as exc:
        upload_path.unlink(missing_ok=True)
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    language = language.strip().lower() or None
    try:
        segments, words = transcribe_video(upload_path, language=language)
        subtitles = whisper_segments_to_subtitles(segments)
    except Exception as exc:  # noqa: BLE001 - keep errors simple for now
        logger.exception("Transcription failed for %s", upload_path)
        raise HTTPException(status_code=500, detail="Transcription failed") from exc

    video_width, video_height = get_video_dimensions(upload_path)
    style = default_style()
    style["play_res_x"] = video_width
    style["play_res_y"] = video_height
    job_data: Dict[str, Any] = {
        "job_id": job_id,
        "title": title.strip() or video.filename,
        "video_filename": safe_name,
        "subtitles": subtitles,
        "style": style,
    }

    karaoke_lines = build_karaoke_lines(words, job_data["subtitles"])
    group_ids = list(range(len(job_data["subtitles"])))
    job_data["subtitles"] = split_subtitles_by_word_timings(
        karaoke_lines, job_data["style"]["max_words_per_line"], group_ids
    ) or split_subtitles_by_words(job_data["subtitles"], job_data["style"]["max_words_per_line"])

    save_subtitle_job(job_id, job_data)
    save_transcript_words(job_id, words)
    touch_job(job_id)
    srt_path = OUTPUTS_DIR / f"{job_id}.srt"
    srt_path.write_text(subtitles_to_srt(job_data["subtitles"]), encoding="utf-8")
    preview_path = OUTPUTS_DIR / f"{job_id}_preview.mp4"
    preview_ass_path = OUTPUTS_DIR / f"{job_id}_preview.ass"
    try:
        karaoke_lines = build_karaoke_lines(words, job_data["subtitles"])
        generate_karaoke_ass(karaoke_lines, preview_ass_path, job_data["style"])
        fonts_dir = ensure_font_downloaded(job_data["style"].get("font_family")) or font_dir_for_name(
            job_data["style"].get("font_family")
        )
        burn_in_ass(upload_path, preview_ass_path, preview_path, fonts_dir)
    except RuntimeError as exc:
        logger.exception("Preview burn-in failed for %s", preview_path)
        raise HTTPException(status_code=500, detail="Preview generation failed") from exc

    return RedirectResponse(url=f"/edit/{job_id}", status_code=303)
