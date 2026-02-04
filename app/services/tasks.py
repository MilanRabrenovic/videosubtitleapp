"""Background job task implementations."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Dict

from app.config import OUTPUTS_DIR, UPLOADS_DIR
from app.services.fonts import ensure_font_downloaded, font_dir_for_name, find_system_font_variant, resolve_font_file
from app.services.jobs import complete_step, fail_step, start_step
from app.services.subtitles import (
    build_karaoke_lines,
    default_style,
    generate_ass_from_subtitles,
    generate_karaoke_ass,
    load_subtitle_job,
    load_transcript_words,
    save_subtitle_job,
    save_transcript_words,
    split_subtitles_by_word_timings,
    split_subtitles_by_words,
    subtitles_to_srt,
    whisper_segments_to_subtitles,
)
from app.services.transcription import transcribe_video
from app.services.resync_helper import fill_subtitle_gaps
import re
from app.services.video import (
    burn_in_ass,
    burn_in_ass_on_color,
    generate_waveform,
    get_video_dimensions,
    get_video_duration,
)


def _render_style(job_id: str, style: Dict[str, Any]) -> Dict[str, Any]:
    render_style = dict(style)
    render_style["font_job_id"] = job_id
    return render_style


def _fonts_dir_for_style(style: Dict[str, Any], job_id: str) -> Path | None:
    font_path = style.get("font_path")
    if font_path:
        try:
            candidate = Path(str(font_path))
        except Exception:
            candidate = None
        else:
            if candidate.exists():
                return candidate.parent
    return ensure_font_downloaded(style.get("font_family")) or font_dir_for_name(
        style.get("font_family"), job_id
    )


def _preview_paths(job_id: str) -> tuple[Path, Path]:
    preview_ass_path = OUTPUTS_DIR / f"{job_id}_preview.ass"
    preview_path = OUTPUTS_DIR / f"{job_id}_preview.mp4"
    return preview_ass_path, preview_path


def run_transcription_job(job: Dict[str, Any]) -> Dict[str, Any]:
    """Run transcription and create initial preview."""
    job_id = str(job["job_id"])
    input_data = job.get("input", {})
    video_path = Path(str(input_data.get("video_path", "")))
    options = input_data.get("options", {}) or {}
    language = options.get("language")
    title = options.get("title") or video_path.name
    video_filename = options.get("video_filename") or video_path.name

    start_step(job_id, "transcribe")
    try:
        segments, words = transcribe_video(video_path, language=language)
        subtitles = whisper_segments_to_subtitles(segments)
    except Exception as exc:  # noqa: BLE001
        error_payload = getattr(exc, "error_payload", {"code": "UNKNOWN"})
        fail_step(job_id, "transcribe", error_payload.get("code", "UNKNOWN"))
        raise
    else:
        complete_step(job_id, "transcribe")
    video_width, video_height = get_video_dimensions(video_path)
    video_duration = get_video_duration(video_path) or 0
    waveform_path = OUTPUTS_DIR / f"{job_id}_waveform.png"
    waveform_width = 1200
    try:
        pixels_per_second = 20
        max_width = 30000
        min_width = 1200
        if video_duration > 0:
            waveform_width = max(min_width, min(int(video_duration * pixels_per_second), max_width))
        generate_waveform(video_path, waveform_path, width=waveform_width)
    except Exception:
        waveform_width = 1200

    style = default_style()
    style["play_res_x"] = video_width
    style["play_res_y"] = video_height
    fallback_font_path = resolve_font_file(style.get("font_family"), job_id)
    if not fallback_font_path:
        fallback_font_path = find_system_font_variant(style.get("font_family"), weight=400, italic=False)
    if fallback_font_path:
        style["font_path"] = str(fallback_font_path)
    job_data: Dict[str, Any] = {
        "job_id": job_id,
        "title": title,
        "video_filename": video_filename,
        "subtitles": subtitles,
        "style": style,
        "video_duration": video_duration,
        "waveform_image": f"{job_id}_waveform.png",
        "waveform_width": waveform_width,
    }
    manual_groups = set(job_data.get("manual_groups", []))
    karaoke_lines = build_karaoke_lines(words, job_data["subtitles"], manual_groups)
    group_ids = list(range(len(job_data["subtitles"])))
    job_data["subtitles"] = split_subtitles_by_word_timings(
        karaoke_lines, job_data["style"]["max_words_per_line"], group_ids
    ) or split_subtitles_by_words(job_data["subtitles"], job_data["style"]["max_words_per_line"])

    save_subtitle_job(job_id, job_data)
    # Save a backup of the original state for factory reset
    from app.services.subtitles import save_original_job
    save_original_job(job_id, job_data)
    save_transcript_words(job_id, words)
    srt_path = OUTPUTS_DIR / f"{job_id}.srt"
    srt_path.write_text(subtitles_to_srt(job_data["subtitles"]), encoding="utf-8")

    preview_ass_path, preview_path = _preview_paths(job_id)
    start_step(job_id, "preview_render")
    try:
        manual_groups = set(job_data.get("manual_groups", []))
        karaoke_lines = build_karaoke_lines(words, job_data["subtitles"], manual_groups)
        render_style = _render_style(job_id, job_data["style"])
        generate_karaoke_ass(karaoke_lines, preview_ass_path, render_style)
        fonts_dir = _fonts_dir_for_style(render_style, job_id)
        burn_in_ass(video_path, preview_ass_path, preview_path, fonts_dir)
    except Exception as exc:  # noqa: BLE001
        error_payload = getattr(exc, "error_payload", {"code": "UNKNOWN"})
        fail_step(job_id, "preview_render", error_payload.get("code", "UNKNOWN"))
        raise
    else:
        complete_step(job_id, "preview_render")

    return {
        "subtitle_path": str(OUTPUTS_DIR / f"{job_id}.json"),
        "video_path": str(preview_path),
    }


def run_preview_job(job: Dict[str, Any]) -> Dict[str, Any]:
    """Render a preview video for the current subtitles."""
    input_data = job.get("input", {})
    options = input_data.get("options", {}) or {}
    job_id = str(options.get("subtitle_job_id", job.get("job_id")))
    job_data = load_subtitle_job(job_id)
    if not job_data:
        raise RuntimeError("Subtitle job not found")
    video_path = UPLOADS_DIR / job_data.get("video_filename", "")
    if not video_path.exists():
        raise RuntimeError("Source video not found")
    words = load_transcript_words(job_id)
    waveform_path = OUTPUTS_DIR / f"{job_id}_waveform.png"
    if not waveform_path.exists():
        video_duration = job_data.get("video_duration") or get_video_duration(video_path) or 0
        pixels_per_second = 20
        max_width = 30000
        min_width = 1200
        waveform_width = max(
            min_width,
            min(int(video_duration * pixels_per_second), max_width),
        )
        try:
            generate_waveform(video_path, waveform_path, width=waveform_width)
            job_data["waveform_width"] = waveform_width
            save_subtitle_job(job_id, job_data)
        except Exception:
            pass
    preview_ass_path, preview_path = _preview_paths(job_id)
    render_style = _render_style(job_id, job_data.get("style", {}))
    start_step(job_id, "preview_render")
    try:
        # Fill gaps for seamless playback of preview
        filled_subtitles = fill_subtitle_gaps(job_data.get("subtitles", []))
        
        if words:
            manual_groups = set(job_data.get("manual_groups", []))
            karaoke_lines = build_karaoke_lines(words, filled_subtitles, manual_groups)
            generate_karaoke_ass(karaoke_lines, preview_ass_path, render_style)
        else:
            generate_ass_from_subtitles(filled_subtitles, preview_ass_path, render_style)
        fonts_dir = _fonts_dir_for_style(render_style, job_id)
        burn_in_ass(video_path, preview_ass_path, preview_path, fonts_dir)
    except Exception as exc:  # noqa: BLE001
        error_payload = getattr(exc, "error_payload", {"code": "UNKNOWN"})
        fail_step(job_id, "preview_render", error_payload.get("code", "UNKNOWN"))
        raise
    else:
        complete_step(job_id, "preview_render")
    return {"subtitle_path": str(OUTPUTS_DIR / f"{job_id}.json"), "video_path": str(preview_path)}


def run_export_job(job: Dict[str, Any]) -> Dict[str, Any]:
    """Export a video with burned subtitles."""
    input_data = job.get("input", {})
    options = input_data.get("options", {}) or {}
    job_id = str(options.get("subtitle_job_id", job.get("job_id")))
    job_data = load_subtitle_job(job_id)
    if not job_data:
        raise RuntimeError("Subtitle job not found")
    video_path = UPLOADS_DIR / job_data.get("video_filename", "")
    if not video_path.exists():
        raise RuntimeError("Source video not found")
    style = job_data.get("style", {})
    render_style = _render_style(job_id, style)
    # Fill gaps for seamless playback of export
    subtitles = fill_subtitle_gaps(job_data.get("subtitles", []))
    words = load_transcript_words(job_id)
    def safe_name(value: str) -> str:
        cleaned = re.sub(r"[^A-Za-z0-9._-]+", "-", value).strip("-")
        return cleaned or "subtitle-export"

    title = str(job_data.get("title") or job_data.get("video_filename") or "subtitle-export")
    base_name = safe_name(Path(title).stem)

    if job.get("type") == "karaoke_export":
        step_name = "export_karaoke"
        if not words:
            error_payload = {"code": "INVALID_MEDIA"}
            fail_step(job_id, step_name, error_payload.get("code", "UNKNOWN"))
            raise RuntimeError("Transcript words not found")
        ass_path = OUTPUTS_DIR / f"{job_id}_karaoke.ass"
        manual_groups = set(job_data.get("manual_groups", []))
        karaoke_lines = build_karaoke_lines(words, subtitles, manual_groups)
        generate_karaoke_ass(karaoke_lines, ass_path, render_style)
        output_path = OUTPUTS_DIR / f"{job_id}_karaoke.mp4"
        download_name = f"{base_name}.mp4"
    elif job.get("type") == "greenscreen_export":
        step_name = "export_greenscreen"
        ass_path = OUTPUTS_DIR / f"{job_id}_greenscreen.ass"
        if words:
            manual_groups = set(job_data.get("manual_groups", []))
            karaoke_lines = build_karaoke_lines(words, subtitles, manual_groups)
            generate_karaoke_ass(karaoke_lines, ass_path, render_style)
        else:
            generate_ass_from_subtitles(subtitles, ass_path, render_style)
        output_path = OUTPUTS_DIR / f"{job_id}_greenscreen.mp4"
        download_name = f"{base_name}_greenscreen.mp4"
    else:
        ass_path = OUTPUTS_DIR / f"{job_id}.ass"
        generate_ass_from_subtitles(subtitles, ass_path, render_style)
        output_path = OUTPUTS_DIR / f"{job_id}_subtitled.mp4"
        download_name = f"{base_name}.mp4"
        step_name = "export_standard"
    fonts_dir = _fonts_dir_for_style(render_style, job_id)
    start_step(job_id, step_name)
    try:
        if job.get("type") == "greenscreen_export":
            width = int(render_style.get("play_res_x") or 1920)
            height = int(render_style.get("play_res_y") or 1080)
            duration = get_video_duration(video_path)
            if not duration:
                raise RuntimeError("Unable to read video duration")
            burn_in_ass_on_color(
                video_path,
                ass_path,
                output_path,
                width,
                height,
                duration,
                fonts_dir,
            )
        else:
            burn_in_ass(video_path, ass_path, output_path, fonts_dir)
    except Exception as exc:  # noqa: BLE001
        error_payload = getattr(exc, "error_payload", {"code": "UNKNOWN"})
        fail_step(job_id, step_name, error_payload.get("code", "UNKNOWN"))
        raise
    else:
        complete_step(job_id, step_name)
    return {
        "subtitle_path": str(OUTPUTS_DIR / f"{job_id}.json"),
        "video_path": str(output_path),
        "download_name": download_name,
    }


def run_job(job: Dict[str, Any]) -> Dict[str, Any]:
    """Dispatch a job by type."""
    job_type = job.get("type")
    if job_type == "transcription":
        return run_transcription_job(job)
    if job_type == "preview":
        return run_preview_job(job)
    if job_type in {"export", "karaoke_export", "greenscreen_export"}:
        return run_export_job(job)
    raise RuntimeError(f"Unknown job type: {job_type}")
