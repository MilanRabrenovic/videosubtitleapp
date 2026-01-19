"""Subtitle editing endpoints."""

import json
import logging
from typing import Any

from fastapi import APIRouter, Form, HTTPException, Request
from fastapi.templating import Jinja2Templates

from app.config import OUTPUTS_DIR, TEMPLATES_DIR, UPLOADS_DIR
from app.services.subtitles import (
    build_karaoke_words,
    default_style,
    generate_karaoke_ass,
    generate_ass_from_subtitles,
    load_subtitle_job,
    load_transcript_words,
    save_subtitle_job,
    subtitles_to_srt,
)
from app.services.video import burn_in_ass

router = APIRouter()
templates = Jinja2Templates(directory=str(TEMPLATES_DIR))
logger = logging.getLogger(__name__)


@router.get("/edit/{job_id}")
def edit_page(request: Request, job_id: str) -> Any:
    """Render the subtitle editing UI."""
    job_data = load_subtitle_job(job_id)
    if not job_data:
        raise HTTPException(status_code=404, detail="Subtitle job not found")

    if "style" not in job_data:
        job_data["style"] = default_style()

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
def save_edits(
    request: Request,
    job_id: str,
    subtitles_json: str = Form(...),
    style_font_family: str = Form(None),
    style_font_size: int = Form(None),
    style_text_color: str = Form(None),
    style_highlight_color: str = Form(None),
    style_outline_color: str = Form(None),
    style_background_enabled: str = Form(None),
    style_background_opacity: float = Form(None),
    style_position: str = Form(None),
    style_margin_v: int = Form(None),
) -> Any:
    """Persist edited subtitles without reprocessing the video."""
    job_data = load_subtitle_job(job_id)
    if not job_data:
        raise HTTPException(status_code=404, detail="Subtitle job not found")

    try:
        subtitles = json.loads(subtitles_json)
    except json.JSONDecodeError as exc:
        raise HTTPException(status_code=400, detail="Invalid subtitle payload") from exc

    style_defaults = default_style()
    style = {
        "font_family": style_font_family or style_defaults["font_family"],
        "font_size": style_font_size or style_defaults["font_size"],
        "text_color": style_text_color or style_defaults["text_color"],
        "highlight_color": style_highlight_color or style_defaults["highlight_color"],
        "outline_color": style_outline_color or style_defaults["outline_color"],
        "background_enabled": style_background_enabled == "on"
        if style_background_enabled is not None
        else style_defaults["background_enabled"],
        "background_opacity": style_background_opacity
        if style_background_opacity is not None
        else style_defaults["background_opacity"],
        "position": style_position or style_defaults["position"],
        "margin_v": style_margin_v if style_margin_v is not None else style_defaults["margin_v"],
    }
    job_data["subtitles"] = subtitles
    job_data["style"] = style
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
                karaoke_words = build_karaoke_words(words, subtitles)
                generate_karaoke_ass(karaoke_words, preview_ass_path, style)
                burn_in_ass(video_path, preview_ass_path, preview_path)
            else:
                generate_ass_from_subtitles(subtitles, preview_ass_path, style)
                burn_in_ass(video_path, preview_ass_path, preview_path)
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
