"""Subtitle editing endpoints."""

import json
from typing import Any

from fastapi import APIRouter, File, Form, HTTPException, Request, UploadFile
from fastapi.templating import Jinja2Templates
from fastapi.responses import RedirectResponse

from app.config import LONG_VIDEO_WARNING_SECONDS, OUTPUTS_DIR, TEMPLATES_DIR, UPLOADS_DIR
from app.services.jobs import create_job, last_failed_step, load_job, touch_job_access, update_job
from app.services.cleanup import touch_job
from app.services.editor import save_subtitle_edits
from app.services.fonts import (
    available_local_fonts,
    delete_font_family,
    detect_font_info_from_path,
    font_files_available,
    google_font_choices,
    guess_font_family,
    google_fonts_css_url,
    is_google_font,
    save_uploaded_font,
    system_font_choices,
)
from app.services.subtitles import default_style, load_subtitle_job, normalize_style
from app.services.presets import builtin_presets, list_user_presets

router = APIRouter()


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
templates = Jinja2Templates(directory=str(TEMPLATES_DIR))


@router.get("/edit/{job_id}")
def edit_page(request: Request, job_id: str) -> Any:
    """Render the subtitle editing UI."""
    user = _require_user(request)
    if not user:
        return RedirectResponse(url="/login", status_code=303)
    if not _ensure_owner(job_id, user["id"]):
        raise HTTPException(status_code=403, detail="Access denied")
    job_data = load_subtitle_job(job_id)
    job_status = None
    job_error = None
    job_failed_step = None
    job_record = load_job(job_id)
    job_pinned = job_record.get("pinned", False) if job_record else False
    user_presets = list_user_presets(user["id"])
    presets_payload = builtin_presets() + [
        {"id": f"user:{preset['id']}", "name": preset["name"], "style": preset["style"]}
        for preset in user_presets
    ]
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
    if "video_duration" not in job_data:
        options = job_record.get("input", {}).get("options", {}) if job_record else {}
        job_data["video_duration"] = options.get("video_duration") or 0
    job_data.setdefault("video_duration", 0)
    job_data.setdefault("waveform_image", f"{job_id}_waveform.png")
    if not job_data.get("waveform_width") and job_data.get("video_duration"):
        pixels_per_second = 20
        max_width = 30000
        min_width = 1200
        job_data["waveform_width"] = max(
            min_width,
            min(int(job_data["video_duration"] * pixels_per_second), max_width),
        )
    job_data.setdefault("waveform_width", 1200)

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
            "long_video_warning": bool(
                job_data.get("video_duration", 0) and job_data["video_duration"] > LONG_VIDEO_WARNING_SECONDS
            ),
            "presets": presets_payload,
            "preset_data_json": json.dumps({p["id"]: p for p in presets_payload}),
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
    style_text_opacity: float = Form(None),
    style_highlight_color: str = Form(None),
    style_highlight_mode: str = Form(None),
    style_highlight_opacity: float = Form(None),
    style_highlight_text_opacity: float = Form(None),
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
    user = _require_user(request)
    if not user:
        return RedirectResponse(url="/login", status_code=303)
    if not _ensure_owner(job_id, user["id"]):
        raise HTTPException(status_code=403, detail="Access denied")
    job_data = load_subtitle_job(job_id)
    if not job_data:
        raise HTTPException(status_code=404, detail="Subtitle job not found")

    try:
        subtitles = json.loads(subtitles_json)
    except json.JSONDecodeError as exc:
        raise HTTPException(status_code=400, detail="Invalid subtitle payload") from exc
    style_form = {
        "font_family": style_font_family,
        "font_size": style_font_size,
        "text_color": style_text_color,
        "text_opacity": style_text_opacity,
        "highlight_color": style_highlight_color,
        "highlight_mode": style_highlight_mode,
        "highlight_opacity": style_highlight_opacity,
        "highlight_text_opacity": style_highlight_text_opacity,
        "outline_color": style_outline_color,
        "outline_enabled": style_outline_enabled == "on" if style_outline_enabled is not None else False,
        "outline_size": style_outline_size,
        "background_color": style_background_color,
        "background_enabled": style_background_enabled == "on" if style_background_enabled is not None else False,
        "background_opacity": style_background_opacity,
        "background_padding": style_background_padding,
        "background_blur": style_background_blur,
        "line_height": style_line_height,
        "position": style_position,
        "margin_v": style_margin_v,
        "max_words_per_line": style_max_words_per_line,
        "font_weight": style_font_weight,
        "font_style": style_font_style,
    }
    session_id = getattr(request.state, "session_id", None)
    data = save_subtitle_edits(
        job_id=job_id,
        subtitles=subtitles,
        style_form=style_form,
        session_id=session_id,
        owner_user_id=int(user["id"]),
    )
    return templates.TemplateResponse(
        "edit.html",
        {
            "request": request,
            "job": data["job"],
            "saved": True,
            "preview_available": data["preview_available"],
            "preview_token": data["preview_token"],
            "waveform_available": data["waveform_available"],
            "waveform_token": data["waveform_token"],
            "preview_job_id": data["preview_job_id"],
            "google_fonts": google_font_choices(),
            "system_fonts": system_font_choices(),
            "custom_fonts": data["custom_fonts"],
            "font_css_url": data["font_css_url"],
            "font_warning": data["font_warning"],
            "job_pinned": data["job_pinned"],
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
    user = _require_user(request)
    if not user:
        return RedirectResponse(url="/login", status_code=303)
    if not _ensure_owner(job_id, user["id"]):
        raise HTTPException(status_code=403, detail="Access denied")
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
            owner_user_id=int(user["id"]),
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
    user = _require_user(request)
    if not user:
        return RedirectResponse(url="/login", status_code=303)
    if not _ensure_owner(job_id, user["id"]):
        raise HTTPException(status_code=403, detail="Access denied")
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
            owner_user_id=int(user["id"]),
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
