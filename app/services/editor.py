"""Editor service helpers for subtitle save flows."""

from __future__ import annotations

from pathlib import Path
import json
import re
from typing import Any

from app.config import FONTS_DIR, LONG_VIDEO_WARNING_SECONDS, OUTPUTS_DIR, UPLOADS_DIR
from app.services.fonts import (
    available_google_font_variants,
    available_local_font_variants,
    available_local_fonts,
    detect_font_info_from_path,
    ensure_font_downloaded,
    find_system_font_variant,
    font_files_available,
    google_fonts_css_url,
    google_font_choices,
    is_google_font,
    normalize_font_name,
    resolve_font_file,
    system_font_choices,
    guess_font_family,
    save_uploaded_font,
)
from app.services.jobs import create_job, load_job, touch_job_access, last_failed_step
from app.services.cleanup import touch_job
from app.services.presets import builtin_presets, list_user_presets
from app.services.subtitles import (
    apply_manual_breaks,
    build_karaoke_lines,
    default_style,
    load_subtitle_job,
    load_transcript_words,
    merge_subtitles_by_group,
    normalize_style,
    save_subtitle_job,
    split_subtitles_by_word_timings,
    split_subtitles_by_words,
    srt_timestamp_to_seconds,
    subtitles_to_srt,
    format_timestamp,
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
    if style_form.get("font_family"):
        style_form["font_family"] = _strip_variant_from_family(str(style_form.get("font_family"))) or style_form.get(
            "font_family"
        )
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
    if style_form.get("font_path"):
        style["font_path"] = style_form.get("font_path")
        style["font_bold"] = False
        style["font_italic"] = str(style.get("font_style", "regular")).lower() == "italic"
        style["font_weight"] = int(style.get("font_weight", 400))
        return style
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
        if best.get("family"):
            style["font_family"] = best.get("family")
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
            style["font_bold"] = False
            style["font_italic"] = bool(is_italic)
            style["font_weight"] = int(weight or desired_weight)
            style["font_style"] = "italic" if style["font_italic"] else "regular"
    if not style.get("font_path"):
        fallback_path = resolve_font_file(style.get("font_family"), job_data.get("job_id"))
        if fallback_path:
            style["font_path"] = str(fallback_path)
    return style


def _strip_variant_from_family(name: str | None) -> str | None:
    if not name:
        return None
    cleaned = re.sub(
        r"(?i)\\b(regular|bold|italic|light|medium|thin|black|semibold|extrabold|extralight)\\b",
        "",
        name,
    )
    cleaned = re.sub(r"(?i)\\b\\d+\\s*pt\\b", "", cleaned)
    cleaned = re.sub(r"\\s+", " ", cleaned).strip()
    return cleaned or name


def _build_presets_payload(user_id: int) -> list[dict[str, Any]]:
    user_presets = list_user_presets(user_id)
    return builtin_presets() + [
        {"id": f"user:{preset['id']}", "name": preset["name"], "style": preset["style"]}
        for preset in user_presets
    ]


def build_edit_context(job_id: str, user_id: int) -> dict[str, Any]:
    job_data = load_subtitle_job(job_id)
    job_status = None
    job_error = None
    job_failed_step = None
    job_record = load_job(job_id)
    job_pinned = job_record.get("pinned", False) if job_record else False
    presets_payload = _build_presets_payload(user_id)
    if not job_data:
        if not job_record:
            raise RuntimeError("Subtitle job not found")
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
    return {
        "job": job_data,
        "preview_available": preview_path.exists(),
        "preview_token": preview_token,
        "waveform_available": waveform_path.exists(),
        "waveform_token": waveform_token,
        "preview_job_id": None,
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
            job_data.get("video_duration", 0)
            and job_data["video_duration"] > LONG_VIDEO_WARNING_SECONDS
        ),
        "presets": presets_payload,
        "preset_data_json": json.dumps({p["id"]: p for p in presets_payload}),
    }


def _save_subtitle_edits_impl(
    *,
    job_id: str,
    subtitles: list[dict[str, Any]],
    style_form: dict[str, Any],
    session_id: str | None,
    owner_user_id: int,
    font_file=None,
    font_family: str = "",
    font_license_confirm: str | None = None,
) -> dict[str, Any]:
    job_data = load_subtitle_job(job_id)
    if not job_data:
        raise RuntimeError("Subtitle job not found")

    job_data["job_id"] = job_id
    if font_file is not None:
        if font_license_confirm != "on":
            raise ValueError("Please confirm font usage rights")
        guessed_family = guess_font_family(getattr(font_file, "filename", "")) or font_family.strip()
        guessed_family = guessed_family or getattr(font_file, "filename", "") or ""
        saved = save_uploaded_font(guessed_family, font_file.filename or "", font_file.file.read(), job_id)
        if not saved:
            raise ValueError("Unsupported font file")
        _, detected_family, detected_full, italic, weight = saved
        display_family = _strip_variant_from_family(detected_family or detected_full)
        job_data["style"] = normalize_style(job_data.get("style"))
        job_data["style"]["font_family"] = display_family
        job_data["style"]["font_bold"] = False
        job_data["style"]["font_italic"] = italic
        job_data["style"]["font_weight"] = int(weight)
        job_data["style"]["font_style"] = "italic" if italic else "regular"
        job_data.setdefault("custom_fonts", [])
        if display_family and display_family not in job_data["custom_fonts"]:
            job_data["custom_fonts"].append(display_family)
        style_form["font_family"] = display_family
        style_form["font_weight"] = int(weight)
        style_form["font_style"] = "italic" if italic else "regular"
        variants = available_local_font_variants(job_id)
        matched_variant = next(
            (
                variant
                for variant in variants
                if variant.get("full_name") == detected_full
                or (
                    variant.get("family") == detected_family
                    and int(variant.get("weight", weight or 0)) == int(weight or 0)
                    and bool(variant.get("italic")) == bool(italic)
                )
            ),
            None,
        )
        if matched_variant and matched_variant.get("path"):
            style_form["font_path"] = str(matched_variant.get("path"))
        else:
            target_dir = FONTS_DIR / "jobs" / job_id
            stem = Path(font_file.filename or "").stem
            suffix = Path(font_file.filename or "").suffix.lower()
            if stem and suffix and target_dir.exists():
                candidates = list(target_dir.glob(f"{stem}-*{suffix}"))
                if candidates:
                    latest = max(candidates, key=lambda p: p.stat().st_mtime)
                    style_form["font_path"] = str(latest)
    style = _build_style(style_form, job_data)
    words = load_transcript_words(job_id)
    previous_blocks = job_data.get("subtitles", [])

    has_manual_pipe = any("|" in str(block.get("text", "")) for block in subtitles)

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

    if has_manual_pipe:
        # Check for multiple pipe segments
        # Find the first block index that contains a pipe
        # Localized Split Strategy:
        # Instead of merging blocks, we iterate and split ONLY the blocks that contain pipes.
        # This prevents "sucking back" later blocks or shifting timelines unwantedly.
        
        # 1. Resync words to current block boundaries (handles any drags/edits)
        from app.services.resync_helper import resync_words_to_blocks
        if words:
             resync_words_to_blocks(words, subtitles)
             
        final_subtitles = []
        collected_lines = []
        
        # We need to manage group_ids carefully to avoid collision?
        # Ideally, we keep existing group_ids unless split.
        
        i = 0
        while i < len(subtitles):
            block = subtitles[i]
            text = str(block.get("text", ""))
            
            if "|" in text:
                # Handle Split
                # Create clean version for alignment
                clean_text = text.replace("|", " ")
                alignment_block = {**block, "text": clean_text}
                
                # Get aligned words for this block
                block_lines = build_karaoke_lines(words, [alignment_block]) if words else [[]]
                
                # Apply split
                split_subs, split_lines = apply_manual_breaks([block], words, base_lines=block_lines)
                
                # Reflow within the split parts if needed (max_words check)
                group_ids = [b.get("group_id") for b in split_subs]
                reflowed_subs = split_subtitles_by_word_timings(
                     split_lines, style["max_words_per_line"], group_ids
                )
                
                # Candidate results for this block
                candidate_subs = reflowed_subs if reflowed_subs else split_subs
                
                # FORWARD MERGE LOGIC:
                # Check if the last part of the split can merge into the NEXT block.
                # This keeps the timeline "tight".
                merged_forward = False
                if candidate_subs and (i + 1 < len(subtitles)):
                    last_part = candidate_subs[-1]
                    next_block = subtitles[i+1]
                    
                    # Check gap
                    last_end = srt_timestamp_to_seconds(str(last_part.get("end", "00:00:00,000")))
                    next_start = srt_timestamp_to_seconds(str(next_block.get("start", "00:00:00,000")))
                    gap = next_start - last_end
                    
                    if gap < 1.0:
                        # Check word counts
                        # We need words for last_part and next_block
                        # We can re-fetch them using build_karaoke_lines helper to be safe
                        last_part_lines = build_karaoke_lines(words, [last_part])
                        next_block_lines = build_karaoke_lines(words, [next_block])
                        
                        last_words = last_part_lines[0] if last_part_lines else []
                        next_words = next_block_lines[0] if next_block_lines else []
                        
                        total_count = len(last_words) + len(next_words)
                        if total_count <= style.get("max_words_per_line", 7):
                            # MERGE!
                            merged_words = last_words + next_words
                            
                            # Create new merged block
                            if merged_words:
                                new_start = merged_words[0].get("start", last_part.get("start"))
                                new_end = merged_words[-1].get("end", next_block.get("end"))
                                new_text = " ".join([w.get("word") for w in merged_words])
                                
                                new_block_obj = {
                                    "start": format_timestamp(float(new_start)),
                                    "end": format_timestamp(float(new_end)),
                                    "text": new_text,
                                    "group_id": next_block.get("group_id") # Inherit next group? Or Keep split group? Usually keeping last is better for flow.
                                }
                                
                                # Replace last part with merged block
                                candidate_subs[-1] = new_block_obj
                                
                                # Skip next block in main loop
                                i += 2
                                merged_forward = True
                            else:
                                i += 1
                        else:
                            i += 1
                    else:
                        i += 1
                else:
                    i += 1
                
                # Add to final results
                final_subtitles.extend(candidate_subs)
                
                # Update collected_lines (words for pills)
                # We need to regenerate lines for the final candidate_subs because we might have merged
                current_lines = build_karaoke_lines(words, candidate_subs)
                collected_lines.extend(current_lines)
                    
            else:
                # Preserve Block
                final_subtitles.append(block)
                # Capture words for this block for transcript_words (pills)
                block_lines = build_karaoke_lines(words, [block]) if words else [[]]
                collected_lines.extend(block_lines)
                i += 1
        
        subtitles = final_subtitles
        manual_lines = collected_lines
        manual_groups = {block.get("group_id") for block in subtitles if block.get("group_id") is not None}
    else:
        # Process ALL blocks.
        # Check if max_words_per_line changed. If so, we want to "heal" manual splits
        # by merging adjacent groups so text can reflow.
        old_max_words = job_data.get("style", {}).get("max_words_per_line")
        new_max_words = style.get("max_words_per_line")
        
        # If max words changed, or if we want to ensure "first time" behavior,
        # we generally want to respect the new constraint over old manual boundaries.
        max_words_changed = old_max_words != new_max_words
        
        if max_words_changed and subtitles:
             print("DEBUG: Max words changed, merging adjacent groups for reflow.")
             # Sort by start time
             subtitles.sort(key=lambda b: srt_timestamp_to_seconds(str(b.get("start", "00:00:00,000"))))
             
             # Smart Merge: Re-assign group IDs based on temporal proximity.
             # If a gap > 1.0s exists (user deletion), we FORCE a start of a new group.
             # This prevents the reflow logic from "sucking back" text across manual gaps.
             
             next_group_id = 1
             subtitles[0]["group_id"] = next_group_id
             last_end = srt_timestamp_to_seconds(str(subtitles[0].get("end", "00:00:00,000")))
             
             for i in range(1, len(subtitles)):
                 block = subtitles[i]
                 start = srt_timestamp_to_seconds(str(block.get("start", "00:00:00,000")))
                 end = srt_timestamp_to_seconds(str(block.get("end", "00:00:00,000")))
                 
                 # Gap Threshold: 1.0 second.
                 # If blocks are closer than this, they merge (allow reflow across).
                 # If further apart, they split (preserve gap).
                 if start - last_end < 1.0:
                     block["group_id"] = next_group_id
                 else:
                     next_group_id += 1
                     block["group_id"] = next_group_id
                 
                 last_end = end

        if subtitles:
            print(f"DEBUG: Processing {len(subtitles)} blocks.")
            
            # ONLY reflow/resplit if the constraint changed.
            # Otherwise, trust the user's current block boundaries (e.g. deletions/moves).
            if max_words_changed:
                print(f"DEBUG: Max words changed ({old_max_words} -> {new_max_words}). Reflowing text.")
                merged_subtitles = merge_subtitles_by_group(subtitles)
                print(f"DEBUG: Merged into {len(merged_subtitles)} groups.")
                
                base_lines = build_karaoke_lines(words, merged_subtitles) if words else [[] for _ in merged_subtitles]
                manual_subtitles, manual_lines = apply_manual_breaks(
                    merged_subtitles, words, base_lines=base_lines
                )
                
                group_ids = [block.get("group_id") for block in manual_subtitles]
                subtitles_split = split_subtitles_by_word_timings(
                    manual_lines, style["max_words_per_line"], group_ids
                )
                
                subtitles = subtitles_split or split_subtitles_by_words(
                    manual_subtitles, style["max_words_per_line"]
                )
            else:
                # No constraint change: Trust the frontend blocks 100%.
                # But we still need 'manual_lines' to reconstruct the transcript_words correctly efficiently.
                # using build_karaoke_lines ensures we get the words that match the remaining blocks
                # and skip the ones that were deleted (gaps).
                print("DEBUG: Max words unchanged. Preserving block structure.")
                
                # Resync word-level timings to match the new user-defined block boundaries.
                # This ensures that if the user dragged a block, the words inside it move with it.
                from app.services.resync_helper import resync_words_to_blocks
                if words:
                     resync_words_to_blocks(words, subtitles)
                
                manual_lines = build_karaoke_lines(words, subtitles) if words else []

        else:
            subtitles = []

        subtitles = sorted(
            subtitles,
            key=lambda b: srt_timestamp_to_seconds(str(b.get("start", "00:00:00,000"))),
        )

    job_data["subtitles"] = subtitles
    job_data["manual_groups"] = sorted(
        {group_id for group_id in manual_groups if group_id is not None}
    )
    job_data["style"] = style
    job_data.setdefault("custom_fonts", [])
    
    # Save the updated word-level timings ("pills") so the frontend can visualize them correctly.
    # This ensures that inserted words,deleted blocks, and timing adjustments are reflected in the UI.
    from app.services.subtitles import save_transcript_words
    
    final_transcript_words = []
    
    # Reconstruct the full list of words
    if "manual_lines" in locals() and manual_lines:
         for line in manual_lines:
             for w in line:
                 clean_w = {k: v for k, v in w.items() if not k.startswith("_")}
                 final_transcript_words.append(clean_w)
         
    
    # Sort just in case
    final_transcript_words.sort(key=lambda w: float(w.get("start", 0.0)))
    
    if final_transcript_words:
        save_transcript_words(job_id, final_transcript_words)

    save_subtitle_job(job_id, job_data)
    
    # Export Processing: Gap Filling
    # Create a copy for export so we don't mutate the editable timeline.
    from app.services.resync_helper import fill_subtitle_gaps
    export_subtitles = fill_subtitle_gaps(subtitles)

    srt_path = OUTPUTS_DIR / f"{job_id}.srt"
    srt_path.write_text(subtitles_to_srt(export_subtitles), encoding="utf-8")
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


def save_subtitle_edits(*args, **kwargs) -> dict[str, Any]:
    try:
        return _save_subtitle_edits_impl(*args, **kwargs)
    except Exception as e:
        import traceback
        error_msg = traceback.format_exc()
        print(f"ERROR in save_subtitle_edits: {error_msg}")
        with open("debug_error.log", "a") as f:
            f.write(f"\nERROR: {error_msg}\n")
        raise


def handle_font_upload(
    *,
    job_id: str,
    font_file,
    font_family: str,
    license_confirmed: bool,
    session_id: str | None,
    owner_user_id: int,
) -> dict[str, Any]:
    if not license_confirmed:
        raise ValueError("Please confirm font usage rights")
    job_data = load_subtitle_job(job_id)
    if not job_data:
        raise RuntimeError("Subtitle job not found")
    guessed_family = guess_font_family(getattr(font_file, "filename", "")) or font_family.strip()
    guessed_family = guessed_family or getattr(font_file, "filename", "") or ""
    saved = save_uploaded_font(guessed_family, font_file.filename or "", font_file.file.read(), job_id)
    if not saved:
        raise ValueError("Unsupported font file")
    _, detected_family, detected_full, italic, weight = saved
    display_family = detected_family or _strip_variant_from_family(detected_full) or _strip_variant_from_family(guessed_family)

    job_data["style"] = normalize_style(job_data.get("style"))
    job_data["style"]["font_family"] = display_family
    job_data["style"]["font_bold"] = False
    job_data["style"]["font_italic"] = italic
    job_data["style"]["font_weight"] = int(weight)
    job_data["style"]["font_style"] = "italic" if italic else "regular"
    job_data.setdefault("custom_fonts", [])
    if display_family and display_family not in job_data["custom_fonts"]:
        job_data["custom_fonts"].append(display_family)
    save_subtitle_job(job_id, job_data)
    touch_job(job_id)
    touch_job_access(job_id)

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

    context = build_edit_context(job_id, owner_user_id)
    context["preview_job_id"] = preview_job_id
    context["preview_available"] = preview_path.exists()
    context["preview_token"] = int(preview_path.stat().st_mtime) if preview_path.exists() else None
    context["waveform_available"] = waveform_path.exists()
    context["waveform_token"] = int(waveform_path.stat().st_mtime) if waveform_path.exists() else None
    return context
