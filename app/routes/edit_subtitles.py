"""Subtitle editing endpoints."""

import json
from typing import Any

from fastapi import APIRouter, File, Form, HTTPException, Request, UploadFile
from fastapi.templating import Jinja2Templates

from app.config import OUTPUTS_DIR, TEMPLATES_DIR, UPLOADS_DIR
from app.services.cleanup import touch_job
from app.services.jobs import create_job, last_failed_step, load_job, touch_job_access
from app.services.fonts import (
    available_local_fonts,
    available_local_font_variants,
    available_google_font_variants,
    delete_font_family,
    ensure_font_downloaded,
    font_files_available,
    google_font_choices,
    guess_font_family,
    google_fonts_css_url,
    is_google_font,
    normalize_font_name,
    save_uploaded_font,
    system_font_choices,
)
from app.services.subtitles import (
    apply_manual_breaks,
    build_karaoke_lines,
    default_style,
    load_subtitle_job,
    load_transcript_words,
    merge_subtitles_by_group,
    normalize_style,
    save_subtitle_job,
    srt_timestamp_to_seconds,
    split_subtitles_by_word_timings,
    split_subtitles_by_words,
    subtitles_to_srt,
)

router = APIRouter()
templates = Jinja2Templates(directory=str(TEMPLATES_DIR))


@router.get("/edit/{job_id}")
def edit_page(request: Request, job_id: str) -> Any:
    """Render the subtitle editing UI."""
    job_data = load_subtitle_job(job_id)
    job_status = None
    job_error = None
    job_failed_step = None
    job_record = load_job(job_id)
    job_pinned = job_record.get("pinned", False) if job_record else False
    if not job_data:
        if not job_record:
            raise HTTPException(status_code=404, detail="Subtitle job not found")
        touch_job_access(job_id, locked=True)
        options = job_record.get("input", {}).get("options", {}) or {}
        job_data = {
            "job_id": job_id,
            "title": options.get("title", "Untitled"),
            "video_filename": options.get("video_filename", ""),
            "subtitles": [],
            "style": default_style(),
        }
        job_status = job_record.get("status")
        job_error = job_record.get("error")
        job_failed_step = last_failed_step(job_record) if job_record else None
    else:
        touch_job(job_id)
        touch_job_access(job_id, locked=True)

    job_data["style"] = normalize_style(job_data.get("style"))
    for index, block in enumerate(job_data["subtitles"]):
        block.setdefault("group_id", index)
    job_data.setdefault("custom_fonts", [])
    job_data.setdefault("video_duration", 0)
    job_data.setdefault("waveform_image", f"{job_id}_waveform.png")

    preview_path = OUTPUTS_DIR / f"{job_id}_preview.mp4"
    waveform_path = OUTPUTS_DIR / f"{job_id}_waveform.png"
    preview_job_id = None
    preview_token = int(preview_path.stat().st_mtime) if preview_path.exists() else None
    waveform_token = int(waveform_path.stat().st_mtime) if waveform_path.exists() else None
    font_css = None
    font_family = job_data["style"].get("font_family")
    font_warning = None
    if is_google_font(font_family):
        font_css = google_fonts_css_url(font_family)
        if not font_files_available(font_family):
            font_warning = (
                f"Font '{font_family}' is not available locally. "
                "Install it. Or place the TTF/OTF files in outputs/fonts/"
                f"{font_family.replace(' ', '-')}/."
            )
    job_custom_fonts = job_data.get("custom_fonts") or available_local_fonts(job_id)
    job_record = load_job(job_id)
    job_pinned = job_record.get("pinned", False) if job_record else False
    return templates.TemplateResponse(
        "edit.html",
        {
            "request": request,
            "job": job_data,
            "preview_available": preview_path.exists(),
            "preview_token": preview_token,
            "waveform_available": waveform_path.exists(),
            "waveform_token": waveform_token,
            "preview_job_id": preview_job_id,
            "google_fonts": google_font_choices(),
            "system_fonts": system_font_choices(),
            "custom_fonts": job_custom_fonts,
            "font_css_url": font_css,
            "font_warning": font_warning,
            "processing_job_id": job_id if job_status in {"queued", "running"} else None,
            "processing_job_status": job_status,
            "processing_job_error": job_error,
            "processing_job_step": job_failed_step,
            "job_pinned": job_pinned,
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
    style_font_weight: int = Form(None),
    style_font_style: str = Form(None),
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
        "font_weight": style_font_weight if style_font_weight is not None else style_defaults["font_weight"],
        "font_style": style_font_style or style_defaults["font_style"],
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
    desired_weight = int(style.get("font_weight", 400))
    desired_italic = str(style.get("font_style", "regular")).lower() == "italic"
    if is_google_font(style.get("font_family")):
        ensure_font_downloaded(style.get("font_family"))
        variants = available_google_font_variants(style.get("font_family"))
    else:
        variants = available_local_font_variants(job_id)
    matching = [
        variant
        for variant in variants
        if variant.get("family") == style.get("font_family")
        or variant.get("full_name") == style.get("font_family")
    ]
    if matching:
        italic_matches = [variant for variant in matching if variant.get("italic") == desired_italic]
        candidates = italic_matches or matching
        best = min(
            candidates,
            key=lambda variant: abs(int(variant.get("weight", 400)) - desired_weight),
        )
        style["font_family"] = best.get("full_name") or best.get("family")
        style["font_bold"] = False
        style["font_italic"] = bool(best.get("italic"))
        style["font_weight"] = int(best.get("weight", desired_weight))
        style["font_style"] = "italic" if style["font_italic"] else "regular"
    else:
        style["font_bold"] = desired_weight >= 600
        style["font_italic"] = desired_italic
    words = load_transcript_words(job_id)
    previous_blocks = job_data.get("subtitles", [])

    def _group_blocks(blocks: list[dict[str, Any]]) -> dict[int | None, list[dict[str, Any]]]:
        grouped: dict[int | None, list[dict[str, Any]]] = {}
        for block in blocks:
            grouped.setdefault(block.get("group_id"), []).append(block)
        for group_id, group_blocks in grouped.items():
            grouped[group_id] = sorted(
                group_blocks,
                key=lambda b: srt_timestamp_to_seconds(str(b.get("start", "00:00:00,000"))),
            )
        return grouped

    current_grouped = _group_blocks(subtitles)
    previous_grouped = _group_blocks(previous_blocks)
    manual_groups: set[int | None] = set(job_data.get("manual_groups", []))
    for group_id, group_blocks in current_grouped.items():
        previous_group = previous_grouped.get(group_id)
        if not previous_group:
            continue
        if len(group_blocks) != len(previous_group):
            continue
        for index, block in enumerate(group_blocks):
            prev_block = previous_group[index]
            start_new = srt_timestamp_to_seconds(str(block.get("start", "00:00:00,000")))
            end_new = srt_timestamp_to_seconds(str(block.get("end", "00:00:00,000")))
            start_prev = srt_timestamp_to_seconds(str(prev_block.get("start", "00:00:00,000")))
            end_prev = srt_timestamp_to_seconds(str(prev_block.get("end", "00:00:00,000")))
            if abs(start_new - start_prev) > 0.001 or abs(end_new - end_prev) > 0.001:
                manual_groups.add(group_id)
                break

    manual_blocks = [block for block in subtitles if block.get("group_id") in manual_groups]
    auto_blocks = [block for block in subtitles if block.get("group_id") not in manual_groups]

    auto_subtitles: list[dict[str, Any]] = []
    if auto_blocks:
        merged_subtitles = merge_subtitles_by_group(auto_blocks)
        base_lines = build_karaoke_lines(words, merged_subtitles) if words else [[] for _ in merged_subtitles]
        manual_subtitles, manual_lines = apply_manual_breaks(
            merged_subtitles, words, base_lines=base_lines
        )
        group_ids = [block.get("group_id") for block in manual_subtitles]
        subtitles_split = split_subtitles_by_word_timings(
            manual_lines, style["max_words_per_line"], group_ids
        )
        auto_subtitles = subtitles_split or split_subtitles_by_words(
            manual_subtitles, style["max_words_per_line"]
        )

    subtitles = sorted(
        manual_blocks + auto_subtitles,
        key=lambda b: srt_timestamp_to_seconds(str(b.get("start", "00:00:00,000"))),
    )
    job_data["subtitles"] = subtitles
    job_data["manual_groups"] = sorted(
        {group_id for group_id in manual_groups if group_id is not None}
    )
    job_data["style"] = style
    job_data.setdefault("custom_fonts", [])
    save_subtitle_job(job_id, job_data)
    srt_path = OUTPUTS_DIR / f"{job_id}.srt"
    srt_path.write_text(subtitles_to_srt(subtitles), encoding="utf-8")
    touch_job(job_id)
    touch_job_access(job_id, locked=False)
    preview_path = OUTPUTS_DIR / f"{job_id}_preview.mp4"
    waveform_path = OUTPUTS_DIR / f"{job_id}_waveform.png"
    video_path = UPLOADS_DIR / job_data.get("video_filename", "")
    preview_job_id = None
    if video_path.exists():
        session_id = getattr(request.state, "session_id", None)
        preview_job = create_job(
            "preview",
            {"video_path": str(video_path), "options": {"subtitle_job_id": job_id}},
            owner_session_id=session_id,
        )
        preview_job_id = preview_job["job_id"]

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
    waveform_token = int(waveform_path.stat().st_mtime) if waveform_path.exists() else None
    job_custom_fonts = job_data.get("custom_fonts") or available_local_fonts(job_id)
    job_record = load_job(job_id)
    job_pinned = job_record.get("pinned", False) if job_record else False
    return templates.TemplateResponse(
        "edit.html",
        {
            "request": request,
            "job": job_data,
            "saved": True,
            "preview_available": preview_path.exists(),
            "preview_token": preview_token,
            "waveform_available": waveform_path.exists(),
            "waveform_token": waveform_token,
            "preview_job_id": preview_job_id,
            "google_fonts": google_font_choices(),
            "system_fonts": system_font_choices(),
            "custom_fonts": job_custom_fonts,
            "font_css_url": font_css,
            "font_warning": font_warning,
            "job_pinned": job_pinned,
        },
    )


@router.post("/edit/{job_id}/font-upload")
def upload_font(
    request: Request,
    job_id: str,
    font_file: UploadFile = File(...),
    font_family: str = Form(""),
    font_license_confirm: str = Form(None),
) -> Any:
    """Upload a custom font file for ASS rendering."""
    job_data = load_subtitle_job(job_id)
    if not job_data:
        raise HTTPException(status_code=404, detail="Subtitle job not found")
    if font_license_confirm != "on":
        raise HTTPException(status_code=400, detail="Please confirm font usage rights")
    guessed_family = guess_font_family(font_file.filename)
    font_family = guessed_family or font_family.strip() or font_file.filename or ""
    saved = save_uploaded_font(font_family, font_file.filename or "", font_file.file.read(), job_id)
    if not saved:
        raise HTTPException(status_code=400, detail="Unsupported font file")
    saved_dir, detected_family, detected_full, italic, weight = saved

    job_data["style"] = normalize_style(job_data.get("style"))
    job_data["style"]["font_family"] = detected_full
    job_data["style"]["font_bold"] = False
    job_data["style"]["font_italic"] = italic
    job_data["style"]["font_weight"] = int(weight)
    job_data["style"]["font_style"] = "italic" if italic else "regular"
    job_data.setdefault("custom_fonts", [])
    if detected_full and detected_full not in job_data["custom_fonts"]:
        job_data["custom_fonts"].append(detected_full)
    save_subtitle_job(job_id, job_data)
    touch_job(job_id)
    touch_job_access(job_id)

    preview_path = OUTPUTS_DIR / f"{job_id}_preview.mp4"
    waveform_path = OUTPUTS_DIR / f"{job_id}_waveform.png"
    video_path = UPLOADS_DIR / job_data.get("video_filename", "")
    preview_job_id = None
    if video_path.exists():
        session_id = getattr(request.state, "session_id", None)
        preview_job = create_job(
            "preview",
            {"video_path": str(video_path), "options": {"subtitle_job_id": job_id}},
            owner_session_id=session_id,
        )
        preview_job_id = preview_job["job_id"]

    font_css = None
    if is_google_font(detected_family):
        font_css = google_fonts_css_url(detected_family)
    preview_token = int(preview_path.stat().st_mtime) if preview_path.exists() else None
    waveform_token = int(waveform_path.stat().st_mtime) if waveform_path.exists() else None
    job_custom_fonts = job_data.get("custom_fonts") or available_local_fonts(job_id)
    job_record = load_job(job_id)
    job_pinned = job_record.get("pinned", False) if job_record else False
    return templates.TemplateResponse(
        "edit.html",
        {
            "request": request,
            "job": job_data,
            "saved": True,
            "preview_available": preview_path.exists(),
            "preview_token": preview_token,
            "waveform_available": waveform_path.exists(),
            "waveform_token": waveform_token,
            "preview_job_id": preview_job_id,
            "google_fonts": google_font_choices(),
            "system_fonts": system_font_choices(),
            "custom_fonts": job_custom_fonts,
            "font_css_url": font_css,
            "font_warning": None,
            "job_pinned": job_pinned,
        },
    )


@router.post("/edit/{job_id}/font-delete")
def delete_font(
    request: Request,
    job_id: str,
    font_family: str = Form(""),
) -> Any:
    """Delete an uploaded font family and reset to default."""
    job_data = load_subtitle_job(job_id)
    if not job_data:
        raise HTTPException(status_code=404, detail="Subtitle job not found")
    font_family = font_family.strip()
    delete_font_family(font_family, job_id)
    style = normalize_style(job_data.get("style"))
    defaults = default_style()
    style["font_family"] = defaults["font_family"]
    style["font_bold"] = defaults["font_bold"]
    style["font_italic"] = defaults["font_italic"]
    job_data["style"] = style
    custom_fonts = job_data.get("custom_fonts", [])
    if font_family in custom_fonts:
        custom_fonts = [font for font in custom_fonts if font != font_family]
        job_data["custom_fonts"] = custom_fonts
    save_subtitle_job(job_id, job_data)
    touch_job(job_id)
    touch_job_access(job_id)

    preview_path = OUTPUTS_DIR / f"{job_id}_preview.mp4"
    waveform_path = OUTPUTS_DIR / f"{job_id}_waveform.png"
    video_path = UPLOADS_DIR / job_data.get("video_filename", "")
    preview_job_id = None
    if video_path.exists():
        session_id = getattr(request.state, "session_id", None)
        preview_job = create_job(
            "preview",
            {"video_path": str(video_path), "options": {"subtitle_job_id": job_id}},
            owner_session_id=session_id,
        )
        preview_job_id = preview_job["job_id"]

    job_custom_fonts = job_data.get("custom_fonts") or available_local_fonts(job_id)
    job_record = load_job(job_id)
    job_pinned = job_record.get("pinned", False) if job_record else False
    preview_token = int(preview_path.stat().st_mtime) if preview_path.exists() else None
    waveform_token = int(waveform_path.stat().st_mtime) if waveform_path.exists() else None
    return templates.TemplateResponse(
        "edit.html",
        {
            "request": request,
            "job": job_data,
            "saved": True,
            "preview_available": preview_path.exists(),
            "preview_token": preview_token,
            "waveform_available": waveform_path.exists(),
            "waveform_token": waveform_token,
            "preview_job_id": preview_job_id,
            "google_fonts": google_font_choices(),
            "system_fonts": system_font_choices(),
            "custom_fonts": job_custom_fonts,
            "font_css_url": None,
            "font_warning": None,
            "job_pinned": job_pinned,
        },
    )
