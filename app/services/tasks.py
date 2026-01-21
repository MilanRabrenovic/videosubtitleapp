"""Background job task implementations."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Dict

from app.config import OUTPUTS_DIR, UPLOADS_DIR
from app.services.fonts import ensure_font_downloaded, font_dir_for_name
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
from app.services.video import burn_in_ass, get_video_dimensions


def _render_style(job_id: str, style: Dict[str, Any]) -> Dict[str, Any]:
    render_style = dict(style)
    render_style["font_job_id"] = job_id
    return render_style


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

    segments, words = transcribe_video(video_path, language=language)
    subtitles = whisper_segments_to_subtitles(segments)
    video_width, video_height = get_video_dimensions(video_path)
    style = default_style()
    style["play_res_x"] = video_width
    style["play_res_y"] = video_height
    job_data: Dict[str, Any] = {
        "job_id": job_id,
        "title": title,
        "video_filename": video_filename,
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
    srt_path = OUTPUTS_DIR / f"{job_id}.srt"
    srt_path.write_text(subtitles_to_srt(job_data["subtitles"]), encoding="utf-8")

    preview_ass_path, preview_path = _preview_paths(job_id)
    karaoke_lines = build_karaoke_lines(words, job_data["subtitles"])
    render_style = _render_style(job_id, job_data["style"])
    generate_karaoke_ass(karaoke_lines, preview_ass_path, render_style)
    fonts_dir = ensure_font_downloaded(job_data["style"].get("font_family")) or font_dir_for_name(
        job_data["style"].get("font_family"), job_id
    )
    burn_in_ass(video_path, preview_ass_path, preview_path, fonts_dir)

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
    preview_ass_path, preview_path = _preview_paths(job_id)
    render_style = _render_style(job_id, job_data.get("style", {}))
    if words:
        karaoke_lines = build_karaoke_lines(words, job_data.get("subtitles", []))
        generate_karaoke_ass(karaoke_lines, preview_ass_path, render_style)
    else:
        generate_ass_from_subtitles(job_data.get("subtitles", []), preview_ass_path, render_style)
    fonts_dir = ensure_font_downloaded(render_style.get("font_family")) or font_dir_for_name(
        render_style.get("font_family"), job_id
    )
    burn_in_ass(video_path, preview_ass_path, preview_path, fonts_dir)
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
    subtitles = job_data.get("subtitles", [])
    words = load_transcript_words(job_id)
    if job.get("type") == "karaoke_export":
        if not words:
            raise RuntimeError("Transcript words not found")
        ass_path = OUTPUTS_DIR / f"{job_id}_karaoke.ass"
        karaoke_lines = build_karaoke_lines(words, subtitles)
        generate_karaoke_ass(karaoke_lines, ass_path, render_style)
        output_path = OUTPUTS_DIR / f"{job_id}_karaoke.mp4"
    else:
        ass_path = OUTPUTS_DIR / f"{job_id}.ass"
        generate_ass_from_subtitles(subtitles, ass_path, render_style)
        output_path = OUTPUTS_DIR / f"{job_id}_subtitled.mp4"
    fonts_dir = ensure_font_downloaded(render_style.get("font_family")) or font_dir_for_name(
        render_style.get("font_family"), job_id
    )
    burn_in_ass(video_path, ass_path, output_path, fonts_dir)
    return {"subtitle_path": str(OUTPUTS_DIR / f"{job_id}.json"), "video_path": str(output_path)}


def run_job(job: Dict[str, Any]) -> Dict[str, Any]:
    """Dispatch a job by type."""
    job_type = job.get("type")
    if job_type == "transcription":
        return run_transcription_job(job)
    if job_type == "preview":
        return run_preview_job(job)
    if job_type in {"export", "karaoke_export"}:
        return run_export_job(job)
    raise RuntimeError(f"Unknown job type: {job_type}")
