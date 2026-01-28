"""Editor service helpers for subtitle save flows."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from app.config import OUTPUTS_DIR, UPLOADS_DIR
from app.services.fonts import (
    available_google_font_variants,
    available_local_font_variants,
    available_local_fonts,
    detect_font_info_from_path,
    ensure_font_downloaded,
    find_system_font_variant,
    font_files_available,
    google_fonts_css_url,
    is_google_font,
    normalize_font_name,
    resolve_font_file,
)
from app.services.jobs import create_job, load_job, touch_job_access
from app.services.cleanup import touch_job
from app.services.subtitles import (
    apply_manual_breaks,
    build_karaoke_lines,
    default_style,
    load_subtitle_job,
    load_transcript_words,
    merge_subtitles_by_group,
    save_subtitle_job,
    split_subtitles_by_word_timings,
    split_subtitles_by_words,
    srt_timestamp_to_seconds,
    subtitles_to_srt,
)


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


def _build_style(style_form: dict[str, Any], job_data: dict[str, Any]) -> dict[str, Any]:
    style_defaults = default_style()
    existing_style = job_data.get("style") or {}
    style = {
        "font_family": style_form.get("font_family") or style_defaults["font_family"],
        "font_size": style_form.get("font_size") or style_defaults["font_size"],
        "font_bold": existing_style.get("font_bold", style_defaults["font_bold"]),
        "font_italic": existing_style.get("font_italic", style_defaults["font_italic"]),
        "font_weight": style_form.get("font_weight")
        if style_form.get("font_weight") is not None
        else style_defaults["font_weight"],
        "font_style": style_form.get("font_style") or style_defaults["font_style"],
        "text_color": style_form.get("text_color") or style_defaults["text_color"],
        "text_opacity": style_form.get("text_opacity")
        if style_form.get("text_opacity") is not None
        else style_defaults["text_opacity"],
        "highlight_color": style_form.get("highlight_color") or style_defaults["highlight_color"],
        "highlight_mode": style_form.get("highlight_mode") or style_defaults["highlight_mode"],
        "highlight_opacity": style_form.get("highlight_opacity")
        if style_form.get("highlight_opacity") is not None
        else style_defaults["highlight_opacity"],
        "highlight_text_opacity": style_form.get("highlight_text_opacity")
        if style_form.get("highlight_text_opacity") is not None
        else style_defaults["highlight_text_opacity"],
        "outline_color": style_form.get("outline_color") or style_defaults["outline_color"],
        "outline_enabled": bool(style_form.get("outline_enabled")),
        "outline_size": style_form.get("outline_size")
        if style_form.get("outline_size") is not None
        else style_defaults["outline_size"],
        "background_color": style_form.get("background_color") or style_defaults["background_color"],
        "background_enabled": bool(style_form.get("background_enabled")),
        "background_opacity": style_form.get("background_opacity")
        if style_form.get("background_opacity") is not None
        else style_defaults["background_opacity"],
        "background_padding": style_form.get("background_padding")
        if style_form.get("background_padding") is not None
        else style_defaults["background_padding"],
        "background_blur": style_form.get("background_blur")
        if style_form.get("background_blur") is not None
        else style_defaults["background_blur"],
        "line_height": style_form.get("line_height")
        if style_form.get("line_height") is not None
        else style_defaults["line_height"],
        "position": style_form.get("position") or style_defaults["position"],
        "margin_v": style_form.get("margin_v")
        if style_form.get("margin_v") is not None
        else style_defaults["margin_v"],
        "single_line": False,
        "max_words_per_line": style_form.get("max_words_per_line")
        if style_form.get("max_words_per_line") is not None
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
        variants = available_local_font_variants(job_data.get("job_id"))
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
        if best.get("path"):
            style["font_path"] = str(best.get("path"))
        style["font_bold"] = False
        style["font_italic"] = bool(best.get("italic"))
        style["font_weight"] = int(best.get("weight", desired_weight))
        style["font_style"] = "italic" if style["font_italic"] else "regular"
    else:
        style["font_bold"] = desired_weight >= 600
        style["font_italic"] = desired_italic
        variant_path = find_system_font_variant(
            style.get("font_family"),
            weight=desired_weight,
            italic=desired_italic,
        )
        if variant_path:
            style["font_path"] = str(variant_path)
            _, full_name, is_italic, weight = detect_font_info_from_path(variant_path)
            if full_name:
                style["font_family"] = full_name
            style["font_bold"] = False
            style["font_italic"] = bool(is_italic)
            style["font_weight"] = int(weight or desired_weight)
            style["font_style"] = "italic" if style["font_italic"] else "regular"
    if not style.get("font_path"):
        fallback_path = resolve_font_file(style.get("font_family"), job_data.get("job_id"))
        if fallback_path:
            style["font_path"] = str(fallback_path)
    return style


def save_subtitle_edits(
    *,
    job_id: str,
    subtitles: list[dict[str, Any]],
    style_form: dict[str, Any],
    session_id: str | None,
    owner_user_id: int,
) -> dict[str, Any]:
    job_data = load_subtitle_job(job_id)
    if not job_data:
        raise RuntimeError("Subtitle job not found")

    job_data["job_id"] = job_id
    style = _build_style(style_form, job_data)
    words = load_transcript_words(job_id)
    previous_blocks = job_data.get("subtitles", [])

    current_grouped = _group_blocks(subtitles)
    previous_grouped = _group_blocks(previous_blocks)
    manual_groups: set[int | None] = set(job_data.get("manual_groups", []))
    for group_id, group_blocks in current_grouped.items():
        previous_group = previous_grouped.get(group_id)
        if not previous_group:
            continue
        if len(group_blocks) != len(previous_group):
            manual_groups.add(group_id)
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
        preview_job = create_job(
            "preview",
            {"video_path": str(video_path), "options": {"subtitle_job_id": job_id}},
            owner_session_id=session_id,
            owner_user_id=int(owner_user_id),
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

    return {
        "job": job_data,
        "preview_available": preview_path.exists(),
        "preview_token": preview_token,
        "waveform_available": waveform_path.exists(),
        "waveform_token": waveform_token,
        "preview_job_id": preview_job_id,
        "custom_fonts": job_custom_fonts,
        "font_css_url": font_css,
        "font_warning": font_warning,
        "job_pinned": job_pinned,
    }
