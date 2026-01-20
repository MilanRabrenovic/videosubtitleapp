"""Subtitle editing endpoints."""

import json
import logging
from typing import Any

from fastapi import APIRouter, File, Form, HTTPException, Request, UploadFile
from fastapi.templating import Jinja2Templates

from app.config import OUTPUTS_DIR, TEMPLATES_DIR, UPLOADS_DIR
from app.services.cleanup import touch_job
from app.services.fonts import (
    available_fonts,
    available_local_fonts,
    ensure_font_downloaded,
    font_dir_for_name,
    font_files_available,
    guess_font_family,
    google_fonts_css_url,
    is_google_font,
    normalize_font_name,
    save_uploaded_font,
)
from app.services.subtitles import (
    apply_manual_breaks,
    build_karaoke_lines,
    default_style,
    generate_karaoke_ass,
    generate_ass_from_subtitles,
    load_subtitle_job,
    load_transcript_words,
    merge_subtitles_by_group,
    normalize_style,
    save_subtitle_job,
    split_subtitles_by_word_timings,
    split_subtitles_by_words,
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
    touch_job(job_id)

    job_data["style"] = normalize_style(job_data.get("style"))
    for index, block in enumerate(job_data["subtitles"]):
        block.setdefault("group_id", index)

    preview_path = OUTPUTS_DIR / f"{job_id}_preview.mp4"
    preview_token = int(preview_path.stat().st_mtime) if preview_path.exists() else None
    font_css = None
    font_family = job_data["style"].get("font_family")
    font_warning = None
    if is_google_font(font_family):
        font_css = google_fonts_css_url(font_family)
        if not font_files_available(font_family):
            font_warning = (
                f"Font '{font_family}' is not available locally. "
                "Install it on the system or place the TTF/OTF files in outputs/fonts/"
                f"{font_family.replace(' ', '-')}/."
            )
    font_choices = sorted(set(list(available_fonts()) + list(available_local_fonts())))
    return templates.TemplateResponse(
        "edit.html",
        {
            "request": request,
            "job": job_data,
            "preview_available": preview_path.exists(),
            "preview_token": preview_token,
            "google_fonts": font_choices,
            "font_css_url": font_css,
            "font_warning": font_warning,
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
    style_outline_enabled: str = Form(None),
    style_outline_size: int = Form(None),
    style_background_color: str = Form(None),
    style_background_enabled: str = Form(None),
    style_background_opacity: float = Form(None),
    style_background_padding: int = Form(None),
    style_background_blur: float = Form(None),
    style_line_height: int = Form(None),
    style_position: str = Form(None),
    style_margin_v: int = Form(None),
    style_max_words_per_line: int = Form(None),
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
    existing_style = job_data.get("style") or {}
    style = {
        "font_family": style_font_family or style_defaults["font_family"],
        "font_size": style_font_size or style_defaults["font_size"],
        "font_bold": existing_style.get("font_bold", style_defaults["font_bold"]),
        "font_italic": existing_style.get("font_italic", style_defaults["font_italic"]),
        "text_color": style_text_color or style_defaults["text_color"],
        "highlight_color": style_highlight_color or style_defaults["highlight_color"],
        "outline_color": style_outline_color or style_defaults["outline_color"],
        "outline_enabled": style_outline_enabled == "on"
        if style_outline_enabled is not None
        else style_defaults["outline_enabled"],
        "outline_size": style_outline_size if style_outline_size is not None else style_defaults["outline_size"],
        "background_color": style_background_color or style_defaults["background_color"],
        "background_enabled": style_background_enabled == "on"
        if style_background_enabled is not None
        else style_defaults["background_enabled"],
        "background_opacity": style_background_opacity
        if style_background_opacity is not None
        else style_defaults["background_opacity"],
        "background_padding": style_background_padding
        if style_background_padding is not None
        else style_defaults["background_padding"],
        "background_blur": style_background_blur
        if style_background_blur is not None
        else style_defaults["background_blur"],
        "line_height": style_line_height if style_line_height is not None else style_defaults["line_height"],
        "position": style_position or style_defaults["position"],
        "margin_v": style_margin_v if style_margin_v is not None else style_defaults["margin_v"],
        "single_line": False,
        "max_words_per_line": style_max_words_per_line
        if style_max_words_per_line is not None
        else style_defaults["max_words_per_line"],
        "play_res_x": existing_style.get("play_res_x"),
        "play_res_y": existing_style.get("play_res_y"),
    }
    canonical_font = normalize_font_name(style.get("font_family"))
    if canonical_font:
        style["font_family"] = canonical_font
    words = load_transcript_words(job_id)
    merged_subtitles = merge_subtitles_by_group(subtitles)
    manual_subtitles, manual_lines = apply_manual_breaks(merged_subtitles, words)
    group_ids = [block.get("group_id") for block in manual_subtitles]
    subtitles_split = split_subtitles_by_word_timings(
        manual_lines, style["max_words_per_line"], group_ids
    )
    subtitles = subtitles_split or split_subtitles_by_words(manual_subtitles, style["max_words_per_line"])
    job_data["subtitles"] = subtitles
    job_data["style"] = style
    save_subtitle_job(job_id, job_data)
    srt_path = OUTPUTS_DIR / f"{job_id}.srt"
    srt_path.write_text(subtitles_to_srt(subtitles), encoding="utf-8")
    touch_job(job_id)
    preview_path = OUTPUTS_DIR / f"{job_id}_preview.mp4"
    preview_ass_path = OUTPUTS_DIR / f"{job_id}_preview.ass"
    video_path = UPLOADS_DIR / job_data.get("video_filename", "")
    fonts_dir = ensure_font_downloaded(style.get("font_family")) or font_dir_for_name(
        style.get("font_family")
    )
    if video_path.exists():
        try:
            if words:
                karaoke_lines = build_karaoke_lines(words, subtitles)
                generate_karaoke_ass(karaoke_lines, preview_ass_path, style)
                burn_in_ass(video_path, preview_ass_path, preview_path, fonts_dir)
            else:
                generate_ass_from_subtitles(subtitles, preview_ass_path, style)
                burn_in_ass(video_path, preview_ass_path, preview_path, fonts_dir)
        except RuntimeError:
            logger.exception("Preview burn-in failed for %s", preview_path)

    font_css = None
    font_family = style.get("font_family")
    font_warning = None
    if is_google_font(font_family):
        font_css = google_fonts_css_url(font_family)
        if not font_files_available(font_family):
            font_warning = (
                f"Font '{font_family}' is not available locally. "
                "Install it on the system or place the TTF/OTF files in outputs/fonts/"
                f"{font_family.replace(' ', '-')}/."
            )
    preview_token = int(preview_path.stat().st_mtime) if preview_path.exists() else None
    font_choices = sorted(set(list(available_fonts()) + list(available_local_fonts())))
    return templates.TemplateResponse(
        "edit.html",
        {
            "request": request,
            "job": job_data,
            "saved": True,
            "preview_available": preview_path.exists(),
            "preview_token": preview_token,
            "google_fonts": font_choices,
            "font_css_url": font_css,
            "font_warning": font_warning,
        },
    )


@router.post("/edit/{job_id}/font-upload")
def upload_font(
    request: Request,
    job_id: str,
    font_file: UploadFile = File(...),
    font_family: str = Form(""),
) -> Any:
    """Upload a custom font file for ASS rendering."""
    job_data = load_subtitle_job(job_id)
    if not job_data:
        raise HTTPException(status_code=404, detail="Subtitle job not found")
    guessed_family = guess_font_family(font_file.filename)
    font_family = guessed_family or font_family.strip() or font_file.filename or ""
    saved = save_uploaded_font(font_family, font_file.filename or "", font_file.file.read())
    if not saved:
        raise HTTPException(status_code=400, detail="Unsupported font file")
    saved_dir, detected_family, detected_full, italic = saved

    job_data["style"] = normalize_style(job_data.get("style"))
    job_data["style"]["font_family"] = detected_full
    job_data["style"]["font_bold"] = False
    job_data["style"]["font_italic"] = italic
    save_subtitle_job(job_id, job_data)
    touch_job(job_id)

    subtitles = job_data.get("subtitles", [])
    words = load_transcript_words(job_id)
    preview_path = OUTPUTS_DIR / f"{job_id}_preview.mp4"
    preview_ass_path = OUTPUTS_DIR / f"{job_id}_preview.ass"
    video_path = UPLOADS_DIR / job_data.get("video_filename", "")
    if video_path.exists():
        try:
            if words:
                karaoke_lines = build_karaoke_lines(words, subtitles)
                generate_karaoke_ass(karaoke_lines, preview_ass_path, job_data["style"])
                burn_in_ass(video_path, preview_ass_path, preview_path, saved_dir)
            else:
                generate_ass_from_subtitles(subtitles, preview_ass_path, job_data["style"])
                burn_in_ass(video_path, preview_ass_path, preview_path, saved_dir)
        except RuntimeError:
            logger.exception("Preview burn-in failed for %s", preview_path)

    font_css = None
    if is_google_font(detected_family):
        font_css = google_fonts_css_url(detected_family)
    preview_token = int(preview_path.stat().st_mtime) if preview_path.exists() else None
    font_choices = sorted(set(list(available_fonts()) + list(available_local_fonts())))
    return templates.TemplateResponse(
        "edit.html",
        {
            "request": request,
            "job": job_data,
            "saved": True,
            "preview_available": preview_path.exists(),
            "preview_token": preview_token,
            "google_fonts": font_choices,
            "font_css_url": font_css,
            "font_warning": None,
        },
    )
