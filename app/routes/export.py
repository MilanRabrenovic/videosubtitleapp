"""Export endpoints for subtitles and rendered video."""

from typing import Any

import logging

from fastapi import APIRouter, Form, HTTPException, Request
from fastapi.responses import FileResponse

from app.config import OUTPUTS_DIR, UPLOADS_DIR
from app.services.subtitles import (
    generate_karaoke_ass,
    load_subtitle_job,
    load_transcript_words,
    subtitles_to_srt,
    subtitles_to_vtt,
)
from app.services.video import burn_in_ass, burn_in_subtitles

router = APIRouter()
logger = logging.getLogger(__name__)


@router.post("/export/{job_id}/subtitles")
def export_subtitles(request: Request, job_id: str, format: str = Form("srt")) -> Any:
    """Export subtitles in SRT or VTT format."""
    job_data = load_subtitle_job(job_id)
    if not job_data:
        raise HTTPException(status_code=404, detail="Subtitle job not found")

    format = format.lower().strip()
    if format not in {"srt", "vtt"}:
        raise HTTPException(status_code=400, detail="Unsupported subtitle format")

    subtitles = job_data.get("subtitles", [])
    output_path = OUTPUTS_DIR / f"{job_id}.{format}"

    if format == "srt":
        output_path.write_text(subtitles_to_srt(subtitles), encoding="utf-8")
        media_type = "text/plain"
    else:
        output_path.write_text(subtitles_to_vtt(subtitles), encoding="utf-8")
        media_type = "text/vtt"

    filename = f"{job_id}.{format}"
    return FileResponse(path=str(output_path), media_type=media_type, filename=filename)


@router.post("/export/{job_id}/video")
def export_video(request: Request, job_id: str) -> Any:
    """Export a video with burned-in subtitles."""
    job_data = load_subtitle_job(job_id)
    if not job_data:
        raise HTTPException(status_code=404, detail="Subtitle job not found")

    video_filename = job_data.get("video_filename")
    if not video_filename:
        raise HTTPException(status_code=400, detail="Missing source video filename")

    video_path = UPLOADS_DIR / video_filename
    if not video_path.exists():
        raise HTTPException(status_code=404, detail="Source video not found")

    subtitles = job_data.get("subtitles", [])
    srt_path = OUTPUTS_DIR / f"{job_id}.srt"
    srt_path.write_text(subtitles_to_srt(subtitles), encoding="utf-8")

    output_path = OUTPUTS_DIR / f"{job_id}_subtitled.mp4"
    try:
        burn_in_subtitles(video_path, srt_path, output_path)
    except RuntimeError as exc:
        logger.exception("FFmpeg export failed for %s", output_path)
        raise HTTPException(status_code=500, detail="FFmpeg failed to export video") from exc

    return FileResponse(
        path=str(output_path),
        media_type="video/mp4",
        filename=output_path.name,
    )


@router.post("/export/{job_id}/video-karaoke")
def export_video_karaoke(request: Request, job_id: str) -> Any:
    """Export a video with burned-in karaoke word highlighting."""
    job_data = load_subtitle_job(job_id)
    if not job_data:
        raise HTTPException(status_code=404, detail="Subtitle job not found")

    video_filename = job_data.get("video_filename")
    if not video_filename:
        raise HTTPException(status_code=400, detail="Missing source video filename")

    video_path = UPLOADS_DIR / video_filename
    if not video_path.exists():
        raise HTTPException(status_code=404, detail="Source video not found")

    words = load_transcript_words(job_id)
    if not words:
        raise HTTPException(status_code=404, detail="Transcript words not found")

    ass_path = OUTPUTS_DIR / f"{job_id}_karaoke.ass"
    generate_karaoke_ass(words, ass_path)

    output_path = OUTPUTS_DIR / f"{job_id}_karaoke.mp4"
    try:
        burn_in_ass(video_path, ass_path, output_path)
    except RuntimeError as exc:
        logger.exception("FFmpeg karaoke export failed for %s", output_path)
        raise HTTPException(status_code=500, detail="FFmpeg failed to export karaoke video") from exc

    return FileResponse(
        path=str(output_path),
        media_type="video/mp4",
        filename=output_path.name,
    )
