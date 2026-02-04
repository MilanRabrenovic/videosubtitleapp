"""Subtitle storage and format conversion helpers."""

import json
import re
from pathlib import Path
from typing import Any, Dict, List, Optional

from app.config import OUTPUTS_DIR
from app.services.fonts import detect_font_info_from_path, font_vertical_metrics, resolve_font_file, text_width_px


def job_path(job_id: str) -> Path:
    """Return the JSON path for a subtitle job."""
    return OUTPUTS_DIR / f"{job_id}.json"


def load_subtitle_job(job_id: str) -> Optional[Dict[str, Any]]:
    """Load subtitle job data from disk."""
    path = job_path(job_id)
    if not path.exists():
        return None
    return json.loads(path.read_text(encoding="utf-8"))


def save_subtitle_job(job_id: str, data: Dict[str, Any]) -> None:
    """Persist subtitle job data to disk."""
    path = job_path(job_id)
    path.write_text(json.dumps(data, indent=2), encoding="utf-8")


def transcript_words_path(job_id: str) -> Path:
    """Return the JSON path for word-level transcript data."""
    return OUTPUTS_DIR / f"{job_id}_transcript_words.json"


def save_transcript_words(job_id: str, words: List[Dict[str, Any]]) -> None:
    """Persist word-level transcript data to disk."""
    path = transcript_words_path(job_id)
    path.write_text(json.dumps(words, indent=2), encoding="utf-8")


def load_transcript_words(job_id: str) -> Optional[List[Dict[str, Any]]]:
    """Load word-level transcript data from disk."""
    path = transcript_words_path(job_id)
    if not path.exists():
        return None
    return json.loads(path.read_text(encoding="utf-8"))


def original_job_path(job_id: str) -> Path:
    """Return the JSON path for the original/factory job state."""
    return OUTPUTS_DIR / f"{job_id}_original.json"


def save_original_job(job_id: str, data: Dict[str, Any]) -> None:
    """Persist the original job state to disk."""
    path = original_job_path(job_id)
    path.write_text(json.dumps(data, indent=2), encoding="utf-8")


def load_original_job(job_id: str) -> Optional[Dict[str, Any]]:
    """Load original job state from disk."""
    path = original_job_path(job_id)
    if not path.exists():
        return None
    return json.loads(path.read_text(encoding="utf-8"))


def default_style() -> Dict[str, Any]:
    """Return default subtitle styling values."""
    return {
        "font_family": "Arial",
        "font_size": 48,
        "font_bold": True,
        "font_italic": False,
        "font_weight": 400,
        "font_style": "regular",
        "text_color": "#FFFFFF",
        "text_opacity": 1.0,
        "highlight_color": "#FFFF00",
        "highlight_mode": "text",
        "highlight_opacity": 1.0,
        "highlight_text_opacity": 1.0,
        "outline_color": "#000000",
        "outline_enabled": True,
        "outline_size": 2,
        "background_color": "#000000",
        "background_enabled": False,
        "background_opacity": 0.6,
        "background_padding": 8,
        "background_blur": 0.0,
        "line_height": 6,
        "position": "bottom",
        "margin_v": 50,
        "single_line": False,
        "max_words_per_line": 7,
    }


def normalize_style(style: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    """Merge user style with defaults."""
    defaults = default_style()
    if not style:
        return defaults
    merged = defaults.copy()
    merged.update({key: value for key, value in style.items() if value is not None})
    return merged


def _clamp01(value: Any, default: float = 1.0) -> float:
    """Clamp numeric values to 0..1 with a safe default."""
    try:
        num = float(value)
    except (TypeError, ValueError):
        return default
    if num < 0.0:
        return 0.0
    if num > 1.0:
        return 1.0
    return num


def _normalize_highlight_mode(value: Any) -> str:
    """Normalize highlight mode strings to a supported value."""
    mode = str(value or "text").lower().strip()
    allowed = {"text", "text_cumulative", "background", "background_cumulative"}
    return mode if mode in allowed else "text"


def _ass_text_tag(color: str, alpha: int) -> str:
    """Build ASS primary color + alpha tag."""
    return f"\\1c{color}&\\1a&H{alpha:02X}&"


def _ass_outline_tag(style: Dict[str, Any]) -> str:
    """Build ASS outline tag for current style."""
    outline_enabled = bool(style.get("outline_enabled", True))
    outline_size = int(style.get("outline_size", 2) or 0)
    outline_size = outline_size if outline_enabled else 0
    outline_color = _ass_color(str(style.get("outline_color", "#000000")), 0)
    return f"\\3c{outline_color}&\\bord{outline_size}\\shad0"


def _escape_ass_text(text: str) -> str:
    """Escape ASS control characters in plain text."""
    return text.replace("\\", "\\\\").replace("{", "\\{").replace("}", "\\}")


def _strip_sup_sub_tags(text: str) -> str:
    """Remove sup/sub markup for measurement."""
    return re.sub(r"(?is)</?(sup|sub)>", "", text)


def _sup_sub_layout(text: str, style: Dict[str, Any]) -> Dict[str, Any]:
    """Return base text, render text (with hidden sup/sub), and overlay metadata."""
    pattern = re.compile(r"(?is)<(sup|sub)>(.*?)</\1>")
    base_parts: List[str] = []
    render_parts: List[str] = []
    overlays: List[Dict[str, Any]] = []
    last_index = 0
    for match in pattern.finditer(text):
        start, end = match.span()
        if start > last_index:
            chunk = text[last_index:start]
            base_parts.append(chunk)
            render_parts.append(_escape_ass_text(chunk))
        content = match.group(2)
        kind = match.group(1).lower()
        start_index = len("".join(base_parts))
        base_parts.append(content)
        render_parts.append(f"{{\\alpha&HFF&}}{_escape_ass_text(content)}{{\\alpha&H00&}}")
        overlays.append({"text": content, "kind": kind, "start": start_index, "length": len(content)})
        last_index = end
    if last_index < len(text):
        tail = text[last_index:]
        base_parts.append(tail)
        render_parts.append(_escape_ass_text(tail))
    return {
        "base_text": "".join(base_parts),
        "render_text": "".join(render_parts),
        "overlays": overlays,
    }


def _format_word_with_alpha(text: str, style: Dict[str, Any]) -> str:
    """Return ASS-safe text with sup/sub content hidden (for overlay rendering)."""
    layout = _sup_sub_layout(text, style)
    return layout["render_text"]


def format_timestamp(seconds: float) -> str:
    """Format seconds as HH:MM:SS,mmm."""
    total_ms = max(0, int(round(seconds * 1000)))
    hours, remainder = divmod(total_ms, 3600 * 1000)
    minutes, remainder = divmod(remainder, 60 * 1000)
    secs, ms = divmod(remainder, 1000)
    return f"{hours:02}:{minutes:02}:{secs:02},{ms:03}"


def whisper_segments_to_subtitles(segments: List[Dict[str, Any]]) -> List[Dict[str, str]]:
    """Convert Whisper segments to the canonical subtitle structure."""
    subtitles: List[Dict[str, str]] = []
    for segment in segments:
        subtitles.append(
            {
                "start": format_timestamp(float(segment["start"])),
                "end": format_timestamp(float(segment["end"])),
                "text": str(segment.get("text", "")).strip(),
            }
        )
    return subtitles


def subtitles_to_srt(subtitles: List[Dict[str, str]]) -> str:
    """Convert subtitle blocks into SRT format."""
    lines: List[str] = []
    for index, block in enumerate(subtitles, start=1):
        start = block.get("start", "00:00:00,000")
        end = block.get("end", "00:00:00,000")
        text = block.get("text", "")
        lines.extend([str(index), f"{start} --> {end}", text, ""])
    return "\n".join(lines).strip() + "\n"


def subtitles_to_vtt(subtitles: List[Dict[str, str]]) -> str:
    """Convert subtitle blocks into VTT format."""
    lines: List[str] = ["WEBVTT", ""]
    for block in subtitles:
        start = block.get("start", "00:00:00,000").replace(",", ".")
        end = block.get("end", "00:00:00,000").replace(",", ".")
        text = block.get("text", "")
        lines.extend([f"{start} --> {end}", text, ""])
    return "\n".join(lines).strip() + "\n"


def srt_timestamp_to_seconds(value: str) -> float:
    """Convert SRT timestamp (HH:MM:SS,mmm) to seconds."""
    try:
        time_part, ms_part = value.split(",")
        hours, minutes, seconds = time_part.split(":")
        return int(hours) * 3600 + int(minutes) * 60 + int(seconds) + int(ms_part) / 1000.0
    except ValueError:
        return 0.0


def split_subtitles_by_words(subtitles: List[Dict[str, Any]], max_words: int) -> List[Dict[str, Any]]:
    """Split subtitle blocks into smaller blocks by word count."""
    if max_words <= 0:
        return subtitles
    split_blocks: List[Dict[str, Any]] = []
    for block in subtitles:
        text = str(block.get("text", "")).strip()
        if not text:
            continue
        words = text.split()
        if len(words) <= max_words:
            split_blocks.append(block)
            continue
        group_id = block.get("group_id")
        start_sec = srt_timestamp_to_seconds(str(block.get("start", "00:00:00,000")))
        end_sec = srt_timestamp_to_seconds(str(block.get("end", "00:00:00,000")))
        if end_sec <= start_sec:
            split_blocks.append(block)
            continue
        total_duration = end_sec - start_sec
        chunks = [words[i : i + max_words] for i in range(0, len(words), max_words)]
        chunk_count = len(chunks)
        for index, chunk_words in enumerate(chunks):
            chunk_start = start_sec + (total_duration * index / chunk_count)
            chunk_end = start_sec + (total_duration * (index + 1) / chunk_count)
            split_blocks.append(
                {
                    "start": format_timestamp(chunk_start),
                    "end": format_timestamp(chunk_end),
                    "text": " ".join(chunk_words),
                    "group_id": group_id,
                }
            )
    return split_blocks


def _join_karaoke_tokens(tokens: List[str]) -> str:
    joined: List[str] = []
    for token in tokens:
        token = str(token).strip()
        if not token:
            continue
        if not joined:
            joined.append(token)
            continue
        if joined[-1].endswith("-"):
            joined[-1] = f"{joined[-1]}{token}"
        else:
            joined.append(token)
    return " ".join(joined).strip()


def split_subtitles_by_word_timings(
    word_lines: List[List[Dict[str, Any]]], max_words: int, group_ids: Optional[List[int]] = None
) -> List[Dict[str, Any]]:
    """Split subtitles using word-level timings for precise start/end times."""
    if max_words <= 0:
        return []
    split_blocks: List[Dict[str, Any]] = []
    last_end = 0.0
    min_gap = 0.2
    for index, line_words in enumerate(word_lines):
        if not line_words:
            continue
        group_id = group_ids[index] if group_ids and index < len(group_ids) else None
        
        # Build chunks respecting max_words AND silence gaps
        chunks = []
        current_chunk = []
        last_word_end = None
        silence_threshold = 0.5

        for word in line_words:
            start = float(word.get("start", 0.0))
            end = float(word.get("end", start))
            
            # Check for silence gap
            is_gap = False
            if last_word_end is not None:
                if (start - last_word_end) > silence_threshold:
                    is_gap = True
            
            if (len(current_chunk) >= max_words) or (is_gap and current_chunk):
                chunks.append(current_chunk)
                current_chunk = []
            
            current_chunk.append(word)
            last_word_end = end
            
        if current_chunk:
            chunks.append(current_chunk)

        for chunk_index, chunk in enumerate(chunks):
            if not chunk:
                continue
            start = float(chunk[0].get("start", 0.0))
            end = float(chunk[-1].get("end", start))
            if start < last_end:
                 start = last_end
            if start < last_end + min_gap and index > 0 and chunk_index == 0:
                 pass 
            
            if start < last_end + 0.05: # Minimal gap
                 start = max(start, last_end + 0.05)
            
            if end < start + 0.1:
                end = start + 0.1
            
            # Sync word timings with the block boundaries
            # If we shifted the block start/end, we should update the boundary words
            # so the pills align perfectly with the block.
            if chunk:
                if float(chunk[0].get("start", 0.0)) < start:
                    chunk[0]["start"] = start
                if float(chunk[-1].get("end", 0.0)) > end:
                    chunk[-1]["end"] = end

            tokens = [str(word.get("word", "")).strip() for word in chunk]
            text = _join_karaoke_tokens(tokens)
            if not text:
                continue
            split_blocks.append(
                {
                    "start": format_timestamp(start),
                    "end": format_timestamp(end),
                    "text": text,
                    "group_id": group_id,
                }
            )
            last_end = end
    return split_blocks


def merge_subtitles_by_group(subtitles: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Merge subtitle blocks by group_id to rebuild original blocks."""
    grouped: Dict[int, List[Dict[str, Any]]] = {}
    fallback_group = 0
    for block in subtitles:
        group_id = block.get("group_id")
        if group_id is None:
            group_id = fallback_group
            fallback_group += 1
        grouped.setdefault(int(group_id), []).append(block)

    merged_blocks: List[Dict[str, Any]] = []
    for group_id, blocks in grouped.items():
        blocks_sorted = sorted(blocks, key=lambda b: srt_timestamp_to_seconds(str(b.get("start", "00:00:00,000"))))
        start = blocks_sorted[0].get("start", "00:00:00,000")
        end = blocks_sorted[-1].get("end", start)
        text = " ".join(str(b.get("text", "")).strip() for b in blocks_sorted).strip()
        merged_blocks.append({"start": start, "end": end, "text": text, "group_id": group_id})

    return sorted(
        merged_blocks,
        key=lambda b: srt_timestamp_to_seconds(str(b.get("start", "00:00:00,000"))),
    )


def _ass_color(hex_color: str, alpha: int = 0) -> str:
    """Convert #RRGGBB to ASS &HAABBGGRR format."""
    color = hex_color.lstrip("#")
    if len(color) != 6:
        color = "FFFFFF"
    rr = color[0:2]
    gg = color[2:4]
    bb = color[4:6]
    return f"&H{alpha:02X}{bb}{gg}{rr}"


def _ass_header(style: Dict[str, Any]) -> str:
    """Build the ASS header with default and optional background styles."""
    style = normalize_style(style)
    font_path = style.get("font_path")
    if font_path:
        try:
            _, full_name, _, _ = detect_font_info_from_path(Path(font_path))
        except Exception:
            full_name = None
        if full_name:
            style["font_family"] = full_name
    background_enabled = bool(style.get("background_enabled"))
    background_opacity = _clamp01(style.get("background_opacity", 0.6), 0.6)
    back_alpha = int(round((1.0 - background_opacity) * 255))
    alignment = {"bottom": 2, "center": 5, "top": 8}.get(style.get("position"), 2)
    margin_v = int(style.get("margin_v", 50))
    outline_value = int(style.get("outline_size", 2))
    bold_flag = -1 if style.get("font_bold", True) else 0
    italic_flag = -1 if style.get("font_italic", False) else 0
    text_opacity = _clamp01(style.get("text_opacity", 1.0), 1.0)
    text_alpha = int(round((1.0 - text_opacity) * 255))
    primary = _ass_color(str(style.get("text_color", "#FFFFFF")), text_alpha)
    secondary = _ass_color(str(style.get("text_color", "#FFFFFF")), text_alpha)
    back_color = _ass_color(str(style.get("background_color", "#000000")), back_alpha)
    outline = _ass_color(str(style.get("outline_color", "#000000")), 0)
    highlight_opacity = _clamp01(style.get("highlight_opacity", 1.0), 1.0)
    highlight_alpha = int(round((1.0 - highlight_opacity) * 255))
    highlight_back = _ass_color(str(style.get("highlight_color", "#FFFF00")), highlight_alpha)
    back = back_color
    default_back = _ass_color(str(style.get("background_color", "#000000")), 255) if background_enabled else back
    outline_enabled = bool(style.get("outline_enabled", True))
    outline_value = outline_value if outline_enabled else 0
    transparent_text = _ass_color(str(style.get("text_color", "#FFFFFF")), 255)

    wrap_style = "2" if style.get("single_line", True) else "0"
    play_res_x = int(style.get("play_res_x", 1920) or 1920)
    play_res_y = int(style.get("play_res_y", 1080) or 1080)
    header_lines = [
        "[Script Info]",
        "ScriptType: v4.00+",
        f"WrapStyle: {wrap_style}",
        f"PlayResX: {play_res_x}",
        f"PlayResY: {play_res_y}",
        "",
        "[V4+ Styles]",
        "Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, "
        "Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, "
        "MarginR, MarginV, Encoding",
        (
            "Style: Default,"
            f"{style.get('font_family', 'Arial')},{int(style.get('font_size', 48))},"
            f"{primary},{secondary},{outline},{default_back},"
            f"{bold_flag},{italic_flag},0,0,100,100,"
            "0,0,"
            f"1,{outline_value},0,{alignment},80,80,{margin_v},1"
        ),
    ]

    if background_enabled:
        box_outline = int(style.get("background_padding", 8))
        header_lines.append(
            (
                "Style: Box,"
                f"{style.get('font_family', 'Arial')},{int(style.get('font_size', 48))},"
                f"{transparent_text},{transparent_text},{back},{back},"
                f"{bold_flag},{italic_flag},0,0,100,100,"
                "0,0,"
                f"3,{box_outline},0,{alignment},80,80,{margin_v},1"
            )
        )

    word_box_outline = int(style.get("background_padding", 8))
    header_lines.append(
        (
            "Style: WordBox,"
            f"{style.get('font_family', 'Arial')},{int(style.get('font_size', 48))},"
            f"{transparent_text},{transparent_text},{highlight_back},{highlight_back},"
            f"{bold_flag},{italic_flag},0,0,100,100,"
            "0,0,"
            f"3,{word_box_outline},0,{alignment},80,80,{margin_v},1"
        )
    )

    header_lines.extend(
        [
            "",
            "[Events]",
            "Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text",
        ]
    )
    return "\n".join(header_lines)


def _single_line_text(text: str, style: Dict[str, Any]) -> str:
    """Force subtitle text to a single line if enabled."""
    if not style.get("single_line", True):
        return text
    return " ".join(text.replace("|", " ").replace("\r", " ").replace("\n", " ").split())


def _apply_single_line_override(text: str, style: Dict[str, Any]) -> str:
    """Apply ASS override to prevent line wrapping when enabled."""
    if not style.get("single_line", True):
        return text
    return "{\\q2}" + text


def _background_blur_tag(style: Dict[str, Any]) -> str:
    """Return a blur tag to soften the background box edges."""
    blur_value = float(style.get("background_blur", 0.0))
    if blur_value <= 0:
        return ""
    be_value = min(10, max(0, int(round(blur_value))))
    return f"{{\\blur{blur_value}\\be{be_value}}}"


def _max_chars_per_line(style: Dict[str, Any]) -> int:
    """Estimate a safe max character count based on PlayRes and font size."""
    play_res_x = int(style.get("play_res_x", 1920) or 1920)
    side_padding = 20
    font_size = int(style.get("font_size", 48))
    text_opacity = _clamp01(style.get("text_opacity", 1.0), 1.0)
    text_alpha = int(round((1.0 - text_opacity) * 255))
    safe_width = play_res_x - (side_padding * 2)
    char_width = max(1.0, font_size * 0.5)
    return max(10, int(safe_width / char_width))


def _split_text_lines(text: str, style: Dict[str, Any]) -> List[str]:
    """Split text into lines by max words and estimated max characters."""
    if style.get("single_line", True):
        return [text]
    max_words = int(style.get("max_words_per_line", 7))
    max_chars = _max_chars_per_line(style)
    normalized = text.replace("|", "\n").replace("\r", "")
    segments = [segment for segment in normalized.split("\n") if segment.strip()]
    if not segments:
        return []
    lines: List[str] = []
    for segment in segments:
        words = segment.split()
        current: List[str] = []
        current_len = 0
        for word in words:
            display_word = _strip_sup_sub_tags(word)
            extra = len(display_word) + (1 if current else 0)
            too_many_words = max_words > 0 and len(current) >= max_words
            too_many_chars = max_chars > 0 and (current_len + extra) > max_chars
            if current and (too_many_words or too_many_chars):
                lines.append(" ".join(current))
                current = [word]
                current_len = len(display_word)
                continue
            current.append(word)
            current_len += extra
        if current:
            lines.append(" ".join(current))
    return lines


def _split_word_lines(words: List[Dict[str, Any]], style: Dict[str, Any]) -> List[List[Dict[str, Any]]]:
    """Split timed words into lines using max words and estimated max characters."""
    max_words = int(style.get("max_words_per_line", 7))
    max_chars = _max_chars_per_line(style)
    lines: List[List[Dict[str, Any]]] = []
    current: List[Dict[str, Any]] = []
    current_len = 0
    for word in words:
        token = str(word.get("word", "")).strip()
        if not token:
            continue
        display_token = _strip_sup_sub_tags(token)
        extra = len(display_token) + (1 if current else 0)
        too_many_words = max_words > 0 and len(current) >= max_words
        too_many_chars = max_chars > 0 and (current_len + extra) > max_chars
        if current and (too_many_words or too_many_chars):
            lines.append(current)
            current = [word]
            current_len = len(display_token)
            continue
        current.append(word)
        current_len += extra
    if current:
        lines.append(current)
    return lines


def _line_positions(line_count: int, style: Dict[str, Any]) -> List[Dict[str, int]]:
    """Return positions for each line based on line height and alignment."""
    if line_count <= 0:
        return []
    play_res_x = int(style.get("play_res_x", 1920) or 1920)
    play_res_y = int(style.get("play_res_y", 1080) or 1080)
    margin_v = int(style.get("margin_v", 50))
    font_size = int(style.get("font_size", 48))
    line_height = float(style.get("line_height", 0))
    padding = int(style.get("background_padding", 0)) if style.get("background_enabled") else 0
    line_step = font_size + (padding * 2) + line_height
    if line_step <= 0:
        line_step = font_size
    position = style.get("position", "bottom")
    if position == "top":
        alignment = 8
        base_y = margin_v
        offset = 0
    elif position == "center":
        alignment = 5
        base_y = play_res_y / 2.0
        offset = (line_count - 1) / 2.0
    else:
        alignment = 2
        base_y = play_res_y - margin_v
        offset = line_count - 1
    positions: List[Dict[str, int]] = []
    for index in range(line_count):
        y = base_y + (index - offset) * line_step
        positions.append(
            {"x": int(round(play_res_x / 2)), "y": int(round(y)), "alignment": alignment}
        )
    return positions


def _overlay_dialogues(
    overlays: List[Dict[str, Any]],
    base_text: str,
    pos: Dict[str, int],
    style: Dict[str, Any],
    start: float,
    end: float,
    format_ass_time,
    word_spans: Optional[List[Dict[str, Any]]] = None,
    highlight_mode: Optional[str] = None,
    highlight_color: Optional[str] = None,
    base_color: Optional[str] = None,
) -> List[str]:
    """Create extra dialogue lines for sup/sub overlays."""
    if not overlays or not base_text:
        return []
    if highlight_mode is not None:
        highlight_mode = _normalize_highlight_mode(highlight_mode)
    font_size = int(style.get("font_size", 48))
    small_size = max(8, int(round(font_size * 0.6)))
    text_opacity = _clamp01(style.get("text_opacity", 1.0), 1.0)
    text_alpha = int(round((1.0 - text_opacity) * 255))
    highlight_text_opacity = _clamp01(style.get("highlight_text_opacity", 1.0), 1.0)
    highlight_alpha = int(round((1.0 - highlight_text_opacity) * 255))
    outline_enabled = bool(style.get("outline_enabled", True))
    outline_size = int(style.get("outline_size", 2) or 0)
    outline_size = outline_size if outline_enabled else 0
    outline_color = _ass_color(str(style.get("outline_color", "#000000")), 0)
    outline_tag = f"\\3c{outline_color}&\\bord{outline_size}\\shad0"
    font_job_id = style.get("font_job_id")
    font_path = resolve_font_file(style.get("font_family"), font_job_id)
    alignment = pos["alignment"]
    metrics = font_vertical_metrics(font_path)
    if metrics:
        ascent, descent, units_per_em = metrics
        height_px = (float(ascent - descent) * float(font_size)) / float(units_per_em)
        ascent_px = (float(ascent) * float(font_size)) / float(units_per_em)
    else:
        height_px = float(font_size)
        ascent_px = float(font_size) * 0.6
    if alignment == 8:
        top_y = pos["y"]
    elif alignment == 5:
        top_y = pos["y"] - (height_px / 2.0)
    else:
        top_y = pos["y"] - height_px
    baseline_y = top_y + ascent_px
    sup_offset = 0.46
    sub_offset = 0.15
    sup_y = baseline_y - (font_size * sup_offset)
    sub_y = baseline_y + (small_size * sub_offset)
    dialogues: List[str] = []
    for overlay in overlays:
        text = str(overlay.get("text", "")).strip()
        if not text:
            continue
        start_index = int(overlay.get("start", 0))
        length = int(overlay.get("length", 0))
        prefix = base_text[:start_index]
        suffix = base_text[start_index + length :]
        overlay_y = sup_y if overlay.get("kind") == "sup" else sub_y
        ass_text = _escape_ass_text(text)
        prefix_text = _escape_ass_text(prefix)
        suffix_text = _escape_ass_text(suffix)
        x_shift = max(1, min(12, int(round(font_size * 0.04))))
        italic_tag = "\\i1" if style.get("font_italic") else "\\i0"
        tag = f"{{\\an5\\pos({pos['x'] - x_shift},{int(round(overlay_y))})\\q2{italic_tag}}}"
        timing_tag = ""
        if word_spans and highlight_mode in {"text", "text_cumulative"} and highlight_color and base_color:
            for span in word_spans:
                if span["start"] <= start_index < span["end"]:
                    rel_start = max(0, int(round((span["start_time"] - start) * 1000)))
                    rel_end = max(rel_start + 1, int(round((span["end_time"] - start) * 1000)))
                    if highlight_mode == "text_cumulative":
                        timing_tag = (
                            f"\\1c{base_color}&\\1a&H{text_alpha:02X}&"
                            f"\\t({rel_start},{rel_start},\\1c{highlight_color}&\\1a&H{highlight_alpha:02X}&)"
                        )
                    else:
                        timing_tag = (
                            f"\\1c{base_color}&\\1a&H{text_alpha:02X}&"
                            f"\\t({rel_start},{rel_start},\\1c{highlight_color}&\\1a&H{highlight_alpha:02X}&)"
                            f"\\t({rel_end},{rel_end},\\1c{base_color}&\\1a&H{text_alpha:02X}&)"
                        )
                    break
        reset_alpha = "\\alpha&H00&"
        if timing_tag:
            main_tag = f"{reset_alpha}{timing_tag}{outline_tag}"
        elif base_color:
            main_tag = f"{reset_alpha}\\1c{base_color}&\\1a&H{text_alpha:02X}&{outline_tag}"
        else:
            main_tag = f"{reset_alpha}\\1a&H{text_alpha:02X}&{outline_tag}"
        overlay_line = (
            f"{{\\alpha&HFE&}}{prefix_text}"
            f"{{{main_tag}}}{{\\fs{small_size}}}{ass_text}{{\\fs{font_size}}}"
            f"{{\\alpha&HFE&}}{suffix_text}{{\\alpha&H00&}}"
        )
        dialogues.append(
            f"Dialogue: 0,{format_ass_time(start)},{format_ass_time(end)},Default,,0,0,0,,{tag}{overlay_line}"
        )
    return dialogues


def _word_box_dialogues(
    words: List[Dict[str, Any]],
    style_data: Dict[str, Any],
    pos: Dict[str, int],
    format_ass_time,
    highlight_color: str,
) -> List[str]:
    """Create per-word rectangle highlight overlays."""
    font_path = None
    raw_font_path = style_data.get("font_path")
    if raw_font_path:
        try:
            font_path = Path(str(raw_font_path))
        except Exception:
            font_path = None
    if not font_path or not font_path.exists():
        font_path = resolve_font_file(style_data.get("font_family"), style_data.get("font_job_id"))
    font_size = int(style_data.get("font_size", 48))
    padding = int(style_data.get("background_padding", 8))
    alignment = int(pos.get("alignment", 2))
    line_height = font_size + padding * 2
    if alignment == 8:
        top_y = int(pos["y"])
    elif alignment == 5:
        top_y = int(round(pos["y"] - line_height / 2))
    else:
        top_y = int(pos["y"] - line_height)
    center_y = int(round(top_y + line_height / 2))

    use_approx = font_path is None
    approx_char = font_size * 0.55
    approx_space = font_size * 0.33

    def measure(text: str) -> Optional[float]:
        if not text:
            return 0.0
        if use_approx:
            return sum(approx_space if ch == " " else approx_char for ch in text)
        width = text_width_px(text, font_path, font_size)
        if width is None:
            return None
        return width

    tokens: List[str] = []
    for word in words:
        token = _strip_sup_sub_tags(str(word.get("word", "")).strip())
        tokens.append(token)
    line_text = " ".join(tokens).strip()
    total_width = measure(line_text)
    if total_width is None:
        use_approx = True
        total_width = measure(line_text) or 0.0
    start_x = int(round(pos["x"] - total_width / 2))

    dialogues: List[str] = []
    for index, word in enumerate(words):
        word_start = float(word.get("start", 0.0))
        word_end = float(word.get("end", word_start))
        if word_end <= word_start:
            continue
        prefix_text = " ".join(tokens[:index]).strip()
        if prefix_text:
            prefix_text += " "
        prefix_width = measure(prefix_text)
        word_width = measure(tokens[index])
        if prefix_width is None or word_width is None:
            use_approx = True
            prefix_width = measure(prefix_text) or 0.0
            word_width = measure(tokens[index]) or approx_char
        cursor_x = float(start_x) + float(prefix_width)
        rect_x = int(round(cursor_x - padding))
        rect_w = int(round(word_width + padding * 2))
        rect_h = int(round(line_height))
        draw = (
            f"{{\\an7\\pos({rect_x},{top_y})\\p1\\1c{highlight_color}&"
            f"\\3c{highlight_color}&\\bord0\\shad0}}"
            f"m 0 0 l {rect_w} 0 l {rect_w} {rect_h} l 0 {rect_h}"
            f"{{\\p0}}"
        )
        dialogues.append(
            f"Dialogue: 0,{format_ass_time(word_start)},{format_ass_time(word_end)},Default,,0,0,0,,{draw}"
        )
    return dialogues


def _word_box_overlay_dialogue(
    words: List[Dict[str, Any]],
    format_ass_time,
    style_data: Dict[str, Any],
    style_name: str,
    override_tag: str = "",
    cumulative: bool = False,
) -> str:
    """Create a dialogue that shows a word-box only during each word's timing."""
    start = float(words[0].get("_line_start", words[0].get("start", 0.0)))
    end = float(words[-1].get("_line_end", words[-1].get("end", start)))
    box_pad = int(style_data.get("background_padding", 8))
    chunks: List[str] = []
    for word in words:
        raw_text = str(word.get("word", "")).strip()
        visible_text = _strip_sup_sub_tags(raw_text)
        word_text = _escape_ass_text(visible_text)
        separator = "" if raw_text.endswith("-") else " "
        word_start = float(word.get("start", start))
        word_end = float(word.get("end", word_start))
        if word_start < start:
            word_start = start
        if word_end > end:
            word_end = end
        rel_start = max(0, int(round((word_start - start) * 1000)))
        rel_end = max(rel_start + 1, int(round((word_end - start) * 1000)))
        if cumulative:
            if rel_start == 0:
                chunks.append(f"{{\\1a&HFF&\\bord{box_pad}}}{word_text}")
            else:
                chunks.append(
                    f"{{\\1a&HFF&\\bord0"
                    f"\\t({rel_start},{rel_start},\\bord{box_pad})}}{word_text}"
                )
        else:
            if rel_start == 0:
                chunks.append(
                    f"{{\\1a&HFF&\\bord{box_pad}"
                    f"\\t({rel_end},{rel_end},\\bord0)}}{word_text}"
                )
            else:
                chunks.append(
                    f"{{\\1a&HFF&\\bord0"
                    f"\\t({rel_start},{rel_start},\\bord{box_pad})"
                    f"\\t({rel_end},{rel_end},\\bord0)}}{word_text}"
                )
        if separator:
            chunks.append("{\\1a&HFF&\\bord0}" + separator)
    text = "".join(chunks).strip()
    if style_data.get("single_line", True):
        text = _single_line_text(text, style_data)
        text = _apply_single_line_override(text, style_data)
    else:
        text = "\\N".join(_split_text_lines(text, style_data))
    if override_tag:
        text = f"{override_tag}{text}"
    return f"Dialogue: 0,{format_ass_time(start)},{format_ass_time(end)},{style_name},,0,0,0,,{text}"


def generate_karaoke_ass(
    word_lines: List[List[Dict[str, Any]]], output_path: Path, style: Optional[Dict[str, Any]] = None
) -> None:
    """Generate an ASS file with karaoke word highlighting."""
    style_data = normalize_style(style)
    highlight_mode = _normalize_highlight_mode(style_data.get("highlight_mode"))
    if highlight_mode in {"background", "background_cumulative"}:
        style_data["text_opacity"] = 1.0
    header = _ass_header(style_data)
    highlight_text_opacity = _clamp01(style_data.get("highlight_text_opacity", 1.0), 1.0)
    highlight_text_alpha = int(round((1.0 - highlight_text_opacity) * 255))
    highlight_color = _ass_color(str(style_data.get("highlight_color", "#FFFF00")), 0)
    base_text_opacity = _clamp01(style_data.get("text_opacity", 1.0), 1.0)
    base_text_alpha = int(round((1.0 - base_text_opacity) * 255))
    base_color = _ass_color(str(style_data.get("text_color", "#FFFFFF")), 0)
    outline_color = _ass_color(str(style_data.get("outline_color", "#000000")), 0)

    def format_ass_time(seconds: float) -> str:
        total_cs = max(0, int(round(seconds * 100)))
        hours, remainder = divmod(total_cs, 3600 * 100)
        minutes, remainder = divmod(remainder, 60 * 100)
        secs, cs = divmod(remainder, 100)
        return f"{hours}:{minutes:02}:{secs:02}.{cs:02}"

    lines: List[str] = [header]
    blur_tag = _background_blur_tag(style_data)
    for line_words in word_lines:
        if not line_words:
            continue
        block_start = float(line_words[0].get("_line_start", line_words[0].get("start", 0.0)))
        block_end = float(line_words[-1].get("_line_end", line_words[-1].get("end", block_start)))
        if style_data.get("single_line", True):
            line_chunks = [line_words]
        else:
            line_chunks = _split_word_lines(line_words, style_data)
        positions = _line_positions(len(line_chunks), style_data)
        for chunk_index, chunk in enumerate(line_chunks):
            if not chunk:
                continue
            chunk_words = [dict(word) for word in chunk]
            chunk_words[0]["_line_start"] = block_start
            chunk_words[-1]["_line_end"] = block_end
            if positions:
                pos = positions[min(chunk_index, len(positions) - 1)]
                pos_tag = f"{{\\an{pos['alignment']}\\pos({pos['x']},{pos['y']})\\q2}}"
            else:
                pos_tag = ""
            plain_text = _join_karaoke_tokens(
                [str(word.get("word", "")).strip() for word in chunk_words]
            ).strip()
            layout = _sup_sub_layout(plain_text, style_data)
            base_text = layout["base_text"]
            render_text = layout["render_text"]
            word_spans: List[Dict[str, Any]] = []
            if highlight_mode in {"text", "text_cumulative"}:
                cursor = 0
                for word in chunk_words:
                    token = _strip_sup_sub_tags(str(word.get("word", "")).strip())
                    if not token:
                        continue
                    idx = base_text.find(token, cursor)
                    if idx < 0:
                        continue
                    span_start = idx
                    span_end = idx + len(token)
                    word_spans.append(
                        {
                            "start": span_start,
                            "end": span_end,
                            "start_time": float(word.get("start", block_start)),
                            "end_time": float(word.get("end", block_start)),
                        }
                    )
                    cursor = span_end
                    if not token.endswith("-") and cursor < len(base_text) and base_text[cursor] == " ":
                        cursor += 1
            overlay_lines = []
            if positions:
                overlay_lines = _overlay_dialogues(
                    layout["overlays"],
                    base_text,
                    pos,
                    style_data,
                    block_start,
                    block_end,
                    format_ass_time,
                    word_spans=word_spans,
                    highlight_mode=highlight_mode,
                    highlight_color=highlight_color,
                    base_color=base_color,
                )
            if style_data.get("background_enabled"):
                lines.append(
                    f"Dialogue: 0,{format_ass_time(block_start)},"
                    f"{format_ass_time(block_end)},"
                    f"Box,,0,0,0,,{blur_tag}{pos_tag}{_escape_ass_text(base_text)}"
                )
            karaoke_style = style_data.copy()
            karaoke_style["single_line"] = True
            if highlight_mode in {"background", "background_cumulative"}:
                box_overlay = _word_box_overlay_dialogue(
                    chunk_words,
                    format_ass_time,
                    karaoke_style,
                    "WordBox",
                    pos_tag,
                    cumulative=highlight_mode == "background_cumulative",
                )
                lines.append(box_overlay)
                base_line = f"{pos_tag}{layout['render_text']}"
                lines.append(
                    f"Dialogue: 0,{format_ass_time(block_start)},"
                    f"{format_ass_time(block_end)},Default,,0,0,0,,{base_line}"
                )
                lines.extend(overlay_lines)
            else:
                dialogue = _build_ass_dialogue(
                    chunk_words,
                    format_ass_time,
                    _format_word_with_alpha,
                    base_color,
                    highlight_color,
                    outline_color,
                    karaoke_style,
                    "Default",
                    pos_tag,
                )
                lines.append(dialogue)
                lines.extend(overlay_lines)

    output_path.write_text("\n".join(lines).strip() + "\n", encoding="utf-8")


def generate_ass_from_subtitles(
    subtitles: List[Dict[str, Any]], output_path: Path, style: Optional[Dict[str, Any]] = None
) -> None:
    """Generate a styled ASS file from subtitle blocks."""
    style_data = normalize_style(style)
    header = _ass_header(style_data)
    lines: List[str] = [header]

    def format_ass_time(seconds: float) -> str:
        total_cs = max(0, int(round(seconds * 100)))
        hours, remainder = divmod(total_cs, 3600 * 100)
        minutes, remainder = divmod(remainder, 60 * 100)
        secs, cs = divmod(remainder, 100)
        return f"{hours}:{minutes:02}:{secs:02}.{cs:02}"

    for block in subtitles:
        start = srt_timestamp_to_seconds(str(block.get("start", "00:00:00,000")))
        end = srt_timestamp_to_seconds(str(block.get("end", "00:00:00,000")))
        if end <= start:
            continue
        raw_text = str(block.get("text", "")).strip()
        if style_data.get("single_line", True):
            text = _single_line_text(raw_text, style_data)
            layout = _sup_sub_layout(text, style_data)
            base_text = layout["base_text"]
            text = layout["render_text"]
            text = _apply_single_line_override(text, style_data)
            if not text:
                continue
            blur_tag = _background_blur_tag(style_data)
            if style_data.get("background_enabled"):
                lines.append(
                    f"Dialogue: 0,{format_ass_time(start)},{format_ass_time(end)},Box,,0,0,0,,{blur_tag}{_escape_ass_text(base_text)}"
                )
            lines.append(
                f"Dialogue: 0,{format_ass_time(start)},{format_ass_time(end)},Default,,0,0,0,,{text}"
            )
            positions = _line_positions(1, style_data)
            pos = positions[0] if positions else {"x": 0, "y": 0, "alignment": 2}
            overlay_lines = _overlay_dialogues(layout["overlays"], base_text, pos, style_data, start, end, format_ass_time)
            lines.extend(overlay_lines)
            continue
        line_texts = _split_text_lines(raw_text, style_data)
        if not line_texts:
            continue
        positions = _line_positions(len(line_texts), style_data)
        blur_tag = _background_blur_tag(style_data)
        for line_index, line_text in enumerate(line_texts):
            if not line_text:
                continue
            if positions:
                pos = positions[min(line_index, len(positions) - 1)]
                pos_tag = f"{{\\an{pos['alignment']}\\pos({pos['x']},{pos['y']})\\q2}}"
            else:
                pos_tag = "{\\q2}"
            layout = _sup_sub_layout(line_text, style_data)
            base_text = layout["base_text"]
            ass_text = f"{pos_tag}{layout['render_text']}"
            if style_data.get("background_enabled"):
                lines.append(
                    f"Dialogue: 0,{format_ass_time(start)},{format_ass_time(end)},Box,,0,0,0,,{blur_tag}{pos_tag}{_escape_ass_text(base_text)}"
                )
            lines.append(
                f"Dialogue: 0,{format_ass_time(start)},{format_ass_time(end)},Default,,0,0,0,,{ass_text}"
            )
            lines.extend(
                _overlay_dialogues(layout["overlays"], base_text, pos, style_data, start, end, format_ass_time)
            )

    output_path.write_text("\n".join(lines).strip() + "\n", encoding="utf-8")

def _tokenize_for_match(text: str) -> List[str]:
    tokens: List[str] = []
    for raw in text.split():
        cleaned = _strip_sup_sub_tags(raw)
        core = re.sub(r"^\W+|\W+$", "", cleaned)
        if not core:
            tokens.append(cleaned)
            continue
        if "-" in core:
            parts = [part for part in core.split("-") if part]
            tokens.extend(parts or [core])
        else:
            tokens.append(core)
    return tokens


def _split_token_for_alignment(token: str) -> tuple[List[str], List[str]]:
    cleaned = _strip_sup_sub_tags(token)
    leading = re.match(r"^\W+", cleaned)
    trailing = re.search(r"\W+$", cleaned)
    prefix = leading.group(0) if leading else ""
    suffix = trailing.group(0) if trailing else ""
    core = re.sub(r"^\W+|\W+$", "", cleaned)
    if not core:
        return [token], [cleaned]
    if "-" not in core:
        return [token], [core]
    parts = [part for part in core.split("-") if part]
    if not parts:
        return [token], [core]
    display_parts: List[str] = []
    match_parts: List[str] = []
    for index, part in enumerate(parts):
        display = part
        if index == 0 and prefix:
            display = f"{prefix}{display}"
        if index < len(parts) - 1:
            display = f"{display}-"
        if index == len(parts) - 1 and suffix:
            display = f"{display}{suffix}"
        display_parts.append(display)
        match_parts.append(part)
    return display_parts, match_parts


def build_karaoke_lines(
    words: List[Dict[str, Any]],
    subtitles: List[Dict[str, Any]],
    manual_groups: Optional[set[int]] = None,
) -> List[List[Dict[str, Any]]]:
    """Align word timings to subtitle text, returning word lines per subtitle block."""
    if not subtitles:
        return []

    def parse_timestamp(value: str) -> float:
        try:
            time_part, ms_part = value.split(",")
            hours, minutes, seconds = time_part.split(":")
            return int(hours) * 3600 + int(minutes) * 60 + int(seconds) + int(ms_part) / 1000.0
        except ValueError:
            return 0.0

    aligned_lines: List[List[Dict[str, Any]]] = []
    index = 0
    total_words = len(words)
    for block in subtitles:
        block_text = str(block.get("text", "")).strip()
        if not block_text:
            continue
        block_start = parse_timestamp(str(block.get("start", "00:00:00,000")))
        block_end = parse_timestamp(str(block.get("end", "00:00:00,000")))
        if block_end <= block_start:
            continue

        block_words: List[Dict[str, Any]] = []
        group_id = block.get("group_id")
        manual_mode = manual_groups is not None and group_id in manual_groups
        if manual_mode:
            # Manual timing edits: collect words by time window to keep real durations.
            for word in words:
                word_start = float(word.get("start", 0.0))
                word_end = float(word.get("end", word_start))
                if word_end < block_start:
                    continue
                if word_start > block_end:
                    continue
                block_words.append(word)
        else:
            while index < total_words:
                word = words[index]
                word_start = float(word.get("start", 0.0))
                word_end = float(word.get("end", word_start))
                if word_end < block_start:
                    index += 1
                    continue
                if word_start > block_end:
                    break
                block_words.append(word)
                index += 1

        raw_tokens = block_text.split()
        if not raw_tokens:
            continue
        display_tokens: List[str] = []
        match_tokens: List[str] = []
        for token in raw_tokens:
            display_parts, match_parts = _split_token_for_alignment(token)
            display_tokens.extend(display_parts)
            match_tokens.extend(match_parts)
        if not display_tokens:
            continue
        line_words: List[Dict[str, Any]] = []
        if block_words and len(block_words) == len(match_tokens):
            for token, word in zip(display_tokens, block_words):
                line_words.append(
                    {
                        "word": token,
                        "start": float(word.get("start", block_start)),
                        "end": float(word.get("end", block_start)),
                    }
                )
        elif block_words and match_tokens:
            # Greedy alignment to handle token count mismatches (e.g. "mega-money-wheel" vs "mega", "money", "wheel")
            # This preserves precise timings for matching words and only interpolates local mismatches.
            
            def normalize(s: str) -> str:
                return re.sub(r"\W+", "", s.lower())

            bw_len = len(block_words)
            mt_len = len(match_tokens)
            bw_cursor = 0
            
            # Map each match_token to a list of block_word indices
            alignment_map: Dict[int, List[int]] = {i: [] for i in range(mt_len)}
            
            for i in range(mt_len):
                token_norm = normalize(match_tokens[i])
                if not token_norm: 
                    continue
                
                # look ahead in block_words
                best_match_idx = -1
                
                # Check current cursor first
                if bw_cursor < bw_len:
                    word_norm = normalize(str(block_words[bw_cursor].get("word", "")))
                    if word_norm.startswith(token_norm) or token_norm.startswith(word_norm) or token_norm == word_norm:
                        best_match_idx = bw_cursor
                    # Handle 1-to-N case (one block word covers multiple tokens)
                    # "mega-money-wheel" covers "mega", "money", "wheel"
                    # If we already matched bw_cursor to previous token, check if it still matches
                    elif i > 0 and alignment_map[i-1] and alignment_map[i-1][-1] == bw_cursor:
                        # Re-check if this word covers this token too? 
                        # Simple heuristic: if we didn't advance cursor, reuse it?
                        # Actually simpler: standard greedy forward.
                        pass

                # If no match at cursor, search forward a bit (window of 5)
                if best_match_idx == -1:
                    for offset in range(1, 6):
                        if bw_cursor + offset >= bw_len: break
                        w_norm = normalize(str(block_words[bw_cursor + offset].get("word", "")))
                        if w_norm == token_norm:
                            best_match_idx = bw_cursor + offset
                            break
                
                if best_match_idx != -1:
                    alignment_map[i].append(best_match_idx)
                    # If exact match or close enough, advance cursor
                    # But if 1-to-N (word covers multiple tokens), we might not want to advance yet?
                    # Let's assume 1-to-1 or N-to-1 primarily.
                    # For 1-to-N (hyphens), the word "mega-money-wheel" matches "mega".
                    # We advance cursor? No, we need it for "money".
                    
                    word_full = normalize(str(block_words[best_match_idx].get("word", "")))
                    # If token is just a prefix of word, do not advance cursor effectively?
                    # But we are strictly iterating tokens.
                    # If token == "mega" and word == "megamoneywheel"
                    if len(word_full) > len(token_norm) and word_full.startswith(token_norm):
                        # Partial match. Keep cursor here for next token?
                        # Only if next token is likely part of this word.
                        # For now, let's keep it simple: mapped.
                        # We only advance cursor if we think we exhausted the word.
                        # Simple heuristic: Always update cursor to best_match_idx. 
                        # Only increment if we "used up" the word? 
                        # Let's just rely on the Search Forward to find the next word if we advanced too fast.
                        # OR: just track usage.
                        bw_cursor = best_match_idx 
                        # Don't increment bw_cursor here, let the next token's search start from current.
                        # But we risk reusing same word for unrelated tokens.
                        # Wait, we need to consume words.
                        pass
                    else:
                         bw_cursor = best_match_idx + 1

            # Fill gaps and build lines
            # If a token has no match, interpolate from neighbors.
            for i in range(mt_len):
                mapped_indices = alignment_map[i]
                
                start_time = 0.0
                end_time = 0.0
                
                if mapped_indices:
                    # Use mapped words
                    w_idx = mapped_indices[0]
                    start_time = float(block_words[w_idx].get("start", block_start))
                    end_time = float(block_words[w_idx].get("end", start_time))
                    
                    # If 1 word maps to multiple tokens (e.g. mega-money-wheel -> mega, money, wheel)
                    # We need to distribute duration.
                    # Check how many tokens map to this same w_idx?
                    siblings = [k for k, v in alignment_map.items() if v and v[0] == w_idx]
                    if len(siblings) > 1:
                        total_dur = end_time - start_time
                        rank = siblings.index(i)
                        slice_dur = total_dur / len(siblings)
                        start_time = start_time + (rank * slice_dur)
                        end_time = start_time + slice_dur
                else:
                    # No match. Interpolate.
                    # Find previous matched
                    prev_time = block_start
                    for k in range(i - 1, -1, -1):
                        if alignment_map[k]:
                             # Get end time of that token
                             # Re-calculate to handle logic above
                             # To simplify: Let's first resolve all timings for all tokens, then assign.
                             pass
                             break 
                    # This implies 2-pass approach is better.

            # 2-Pass: Assign Raw Timings, then Interpolate Gaps
            final_timings = []
            for i in range(mt_len):
                indices = alignment_map[i]
                if indices:
                    w_idx = indices[0]
                    # Check siblings
                    siblings = [k for k, v in alignment_map.items() if v and v[0] == w_idx]
                    raw_start = float(block_words[w_idx].get("start", block_start))
                    raw_end = float(block_words[w_idx].get("end", raw_start))
                    
                    if len(siblings) > 1:
                        total_dur = max(0.01, raw_end - raw_start)
                        rank = siblings.index(i)
                        slice_dur = total_dur / len(siblings)
                        s = raw_start + (rank * slice_dur)
                        e = s + slice_dur
                        final_timings.append({"start": s, "end": e, "fixed": True})
                    else:
                        final_timings.append({"start": raw_start, "end": raw_end, "fixed": True})
                else:
                    final_timings.append({"start": 0.0, "end": 0.0, "fixed": False})

            # Pass 2b: Ensure Gaps have Minimum Duration (Gap Expansion)
            # If inserted words (unfixed) have 0 duration, steal from neighbors.
            MIN_INSERT_DURATION = 0.3
            processed_gap_until = -1
            
            for i in range(mt_len):
                if i <= processed_gap_until:
                    continue
                
                if not final_timings[i]["fixed"]:
                    # Found start of a gap
                    gap_start_idx = i
                    gap_end_idx = i
                    for k in range(i + 1, mt_len):
                        if not final_timings[k]["fixed"]:
                            gap_end_idx = k
                        else:
                            break
                    processed_gap_until = gap_end_idx
                    
                    gap_count = gap_end_idx - gap_start_idx + 1
                    required_dur = MIN_INSERT_DURATION * gap_count
                    
                    # Find boundaries
                    left_idx = gap_start_idx - 1
                    right_idx = gap_end_idx + 1
                    
                    left_time = final_timings[left_idx]["end"] if left_idx >= 0 else block_start
                    right_time = final_timings[right_idx]["start"] if right_idx < mt_len else block_end
                    
                    available_dur = max(0.0, right_time - left_time)
                    deficit = required_dur - available_dur
                    
                    if deficit > 0.01:
                        # Try to steal duration from neighbors
                        steal_amount = deficit
                        
                        # Can steal from left?
                        stolen_left = 0.0
                        if left_idx >= 0 and final_timings[left_idx]["fixed"]:
                            l_start = final_timings[left_idx]["start"]
                            l_dur = left_time - l_start
                            # Don't shrink below 0.1s
                            can_steal = max(0.0, l_dur - 0.1)
                            steal_req = steal_amount / 2 # Try splitting evenly
                            if right_idx >= mt_len: # If no right neighbor, take all from left
                                 steal_req = steal_amount
                            
                            actual_steal = min(can_steal, steal_req)
                            # If we need more and right side can't give (not implemented fully), tough luck?
                            # Let's try to take as much as needed up to limit.
                            actual_steal = min(can_steal, steal_amount)
                            
                            if actual_steal > 0:
                                final_timings[left_idx]["end"] -= actual_steal
                                left_time -= actual_steal
                                stolen_left = actual_steal
                                steal_amount -= actual_steal
                        
                        # Can steal from right?
                        if steal_amount > 0.001 and right_idx < mt_len and final_timings[right_idx]["fixed"]:
                            r_end = final_timings[right_idx]["end"]
                            r_dur = r_end - right_time
                            can_steal = max(0.0, r_dur - 0.1)
                            
                            actual_steal = min(can_steal, steal_amount)
                            if actual_steal > 0:
                                final_timings[right_idx]["start"] += actual_steal
                                right_time += actual_steal
                                steal_amount -= actual_steal

            # Interpolate Gaps
            for i in range(mt_len):
                if not final_timings[i]["fixed"]:
                    # Find left neighbor
                    left_time = block_start
                    for k in range(i - 1, -1, -1):
                        if final_timings[k]["fixed"]:
                            left_time = final_timings[k]["end"]
                            break
                    
                    # Find right neighbor
                    right_time = block_end
                    next_fixed_idx = -1
                    for k in range(i + 1, mt_len):
                        if final_timings[k]["fixed"]:
                            right_time = final_timings[k]["start"]
                            next_fixed_idx = k
                            break
                    
                    # Distribute space among consecutive gaps
                    gap_count = 1
                    for k in range(i + 1, next_fixed_idx if next_fixed_idx != -1 else mt_len):
                        if not final_timings[k]["fixed"]:
                            gap_count += 1
                        else:
                            break
                    
                    dur = max(0.0, right_time - left_time)
                    slot = dur / gap_count
                    
                    # Apply to this gap segment
                    gap_idx = 0 # current is 0th in this sequence
                    # Actually just set current
                    final_timings[i]["start"] = left_time
                    final_timings[i]["end"] = left_time + slot
                    final_timings[i]["fixed"] = True # Mark fixed so next one uses it as left neighbor

            # Build line_words
            for index, token in enumerate(display_tokens):
                t_dat = final_timings[index]
                line_words.append({"word": token, "start": t_dat["start"], "end": t_dat["end"]})

        if line_words:
            line_words = _smooth_word_timings(line_words, block_start, block_end, max_duration=None)
            line_words[0]["_line_start"] = block_start
            line_words[-1]["_line_end"] = block_end
            aligned_lines.append(line_words)

    return aligned_lines


def _smooth_word_timings(
    line_words: List[Dict[str, Any]],
    line_start: float,
    line_end: float,
    min_duration: float = 0.04,
    max_duration: Optional[float] = 0.6,
    min_gap: float = 0.01,
) -> List[Dict[str, Any]]:
    """Clamp word durations and prevent overlaps for smoother karaoke timing."""
    if line_end <= line_start:
        return line_words
    prev_end = line_start
    for word in line_words:
        start = max(float(word.get("start", line_start)), prev_end)
        end = float(word.get("end", start))
        duration = end - start
        if duration < min_duration:
            end = start + min_duration
        if max_duration is not None and duration > max_duration:
            end = start + max_duration
        if end > line_end:
            end = line_end
        if end < start + min_gap:
            end = min(line_end, start + min_gap)
        word["start"] = start
        word["end"] = end
        prev_end = end
    return line_words


def _split_text_segments(text: str) -> List[str]:
    """Split text into manual line segments using newlines or | markers."""
    normalized = text.replace("|", "\n")
    segments = [segment.strip() for segment in normalized.splitlines() if segment.strip()]
    return segments or [text.strip()]


def apply_manual_breaks(
    subtitles: List[Dict[str, Any]],
    words: Optional[List[Dict[str, Any]]],
    base_lines: Optional[List[List[Dict[str, Any]]]] = None,
) -> tuple[List[Dict[str, Any]], List[List[Dict[str, Any]]]]:
    """Apply manual line breaks and return updated subtitles and karaoke lines."""
    if base_lines is None:
        base_lines = build_karaoke_lines(words, subtitles) if words else [[] for _ in subtitles]
    new_subtitles: List[Dict[str, Any]] = []
    new_lines: List[List[Dict[str, Any]]] = []
    group_counter = 0

    for index, block in enumerate(subtitles):
        text = str(block.get("text", "")).strip()
        if not text:
            continue
        segments = _split_text_segments(text)
        line_words = base_lines[index] if index < len(base_lines) else []

        if len(segments) == 1:
            new_subtitles.append(
                {
                    "start": block.get("start"),
                    "end": block.get("end"),
                    "text": segments[0],
                    "group_id": group_counter,
                }
            )
            new_lines.append(line_words or [])
            group_counter += 1
            continue

        tokens_per_segment: List[List[str]] = []
        display_tokens_per_segment: List[List[str]] = []
        for segment in segments:
            display_tokens: List[str] = []
            match_tokens: List[str] = []
            for token in segment.split():
                display_parts, match_parts = _split_token_for_alignment(token)
                display_tokens.extend(display_parts)
                match_tokens.extend(match_parts)
            display_tokens_per_segment.append(display_tokens)
            tokens_per_segment.append(match_tokens)
        total_tokens = sum(len(tokens) for tokens in tokens_per_segment)
        block_start = srt_timestamp_to_seconds(str(block.get("start", "00:00:00,000")))
        block_end = srt_timestamp_to_seconds(str(block.get("end", "00:00:00,000")))
        if block_end <= block_start:
            continue

        if len(segments) > 1:
            print(f"DEBUG: apply_manual_breaks breakdown for block {index}")
            print(f"DEBUG: Segments: {segments}")
            print(f"DEBUG: Tokens per segment: {tokens_per_segment}")
            print(f"DEBUG: Total tokens: {total_tokens}")
            print(f"DEBUG: Len line_words: {len(line_words) if line_words else 0}")
            print(f"DEBUG: Len line_words: {len(line_words) if line_words else 0}")
            if line_words:
                 words_debug = [{"w": w.get("word"), "s": w.get("start"), "e": w.get("end")} for w in line_words[:4]]
                 print(f"DEBUG: First 4 line_words: {words_debug}")
                 
        if line_words and total_tokens == len(line_words):

            cursor = 0
            for segment_text, tokens in zip(segments, tokens_per_segment):
                if not tokens:
                    continue
                segment_words = line_words[cursor : cursor + len(tokens)]
                cursor += len(tokens)
                start = float(segment_words[0].get("start", block_start))
                end = float(segment_words[-1].get("end", start))
                new_subtitles.append(
                    {
                        "start": format_timestamp(start),
                        "end": format_timestamp(end),
                        "text": segment_text,
                        "group_id": group_counter,
                    }
                )
                new_lines.append(segment_words)
                group_counter += 1
        else:
            total_tokens = sum(len(tokens) for tokens in tokens_per_segment)
            if total_tokens <= 0:
                continue
            block_duration = max(0.1, block_end - block_start)
            current_time = block_start
            for seg_index, (segment_text, tokens, display_tokens) in enumerate(
                zip(segments, tokens_per_segment, display_tokens_per_segment)
            ):
                if not tokens:
                    continue
                weight = len(tokens) / total_tokens
                segment_duration = block_duration * weight
                start = current_time
                end = block_end if seg_index == len(tokens_per_segment) - 1 else start + segment_duration
                current_time = end
                per_word = max(0.05, (end - start) / len(tokens))
                segment_words = []
                for token_index, token in enumerate(display_tokens):
                    w_start = start + token_index * per_word
                    w_end = w_start + per_word
                    segment_words.append({"word": token, "start": w_start, "end": w_end})
                new_subtitles.append(
                    {
                        "start": format_timestamp(start),
                        "end": format_timestamp(end),
                        "text": segment_text,
                        "group_id": group_counter,
                    }
                )
                new_lines.append(segment_words)
                group_counter += 1

    return new_subtitles, new_lines


def _build_ass_dialogue(
    words: List[Dict[str, Any]],
    format_ass_time,
    format_ass_text,
    base_color: str,
    highlight_color: str,
    outline_color: str,
    style_data: Dict[str, Any],
    style_name: str,
    override_tag: str = "",
) -> str:
    start = float(words[0].get("_line_start", words[0].get("start", 0.0)))
    end = float(words[-1].get("_line_end", words[-1].get("end", start)))
    chunks: List[str] = []
    highlight_mode = _normalize_highlight_mode(style_data.get("highlight_mode"))
    cumulative_text = highlight_mode == "text_cumulative"
    outline_enabled = bool(style_data.get("outline_enabled", True))
    outline_size = int(style_data.get("outline_size", 2) or 0)
    normal_bord = outline_size if outline_enabled else 0
    highlight_bord = max(normal_bord, int(round((style_data.get("background_padding", 8) or 0) / 2)) + 6)
    base_text_opacity = _clamp01(style_data.get("text_opacity", 1.0), 1.0)
    base_alpha = int(round((1.0 - base_text_opacity) * 255))
    highlight_text_opacity = _clamp01(style_data.get("highlight_text_opacity", 1.0), 1.0)
    highlight_alpha = int(round((1.0 - highlight_text_opacity) * 255))
    normal_style = f"{_ass_text_tag(base_color, base_alpha)}{_ass_outline_tag(style_data)}"
    highlight_style = (
        f"{_ass_text_tag(base_color, base_alpha)}"
        f"\\3c{highlight_color}&"
        f"\\bord{highlight_bord}\\xbord{highlight_bord}\\ybord{highlight_bord}\\shad0\\blur0"
    )
    for word in words:
        word_text = format_ass_text(str(word.get("word", "")).strip(), style_data)
        separator = "" if word_text.endswith("-") else " "
        word_start = float(word.get("start", start))
        word_end = float(word.get("end", word_start))
        if word_start < start:
            word_start = start
        if word_end > end:
            word_end = end
        duration = max(1, int(round((word_end - word_start) * 100)))
        rel_start = max(0, int(round((word_start - start) * 1000)))
        rel_end = max(rel_start + 1, int(round((word_end - start) * 1000)))
        karaoke_tag = "" if highlight_mode in {"text", "text_cumulative"} else f"\\k{duration}"
        if highlight_mode in {"background", "background_cumulative"}:
            if rel_start == 0:
                chunks.append(
                    f"{{{karaoke_tag}{highlight_style}"
                    f"\\t({rel_end},{rel_end},{normal_style})}}{word_text}{separator}"
                )
            else:
                chunks.append(
                    f"{{{karaoke_tag}{normal_style}"
                    f"\\t({rel_start},{rel_start},{highlight_style})"
                    f"\\t({rel_end},{rel_end},{normal_style})}}{word_text}{separator}"
                )
        else:
            if rel_start == 0:
                if cumulative_text:
                    chunks.append(
                        f"{{{karaoke_tag}\\1c{highlight_color}&\\1a&H{highlight_alpha:02X}&}}{word_text}{separator}"
                    )
                else:
                    chunks.append(
                        f"{{{karaoke_tag}\\1c{highlight_color}&\\1a&H{highlight_alpha:02X}&"
                        f"\\t({rel_end},{rel_end},\\1c{base_color}&\\1a&H{base_alpha:02X}&)}}{word_text}{separator}"
                    )
            else:
                if cumulative_text:
                    chunks.append(
                        f"{{{karaoke_tag}\\1c{base_color}&\\1a&H{base_alpha:02X}&"
                        f"\\t({rel_start},{rel_start},\\1c{highlight_color}&\\1a&H{highlight_alpha:02X}&)}}{word_text}{separator}"
                    )
                else:
                    chunks.append(
                        f"{{{karaoke_tag}\\1c{base_color}&\\1a&H{base_alpha:02X}&"
                        f"\\t({rel_start},{rel_start},\\1c{highlight_color}&\\1a&H{highlight_alpha:02X}&)"
                        f"\\t({rel_end},{rel_end},\\1c{base_color}&\\1a&H{base_alpha:02X}&)}}{word_text}{separator}"
                    )
    text = "".join(chunks).strip()
    if style_data.get("single_line", True):
        text = _single_line_text(text, style_data)
        text = _apply_single_line_override(text, style_data)
    else:
        text = "\\N".join(_split_text_lines(text, style_data))
    if override_tag:
        text = f"{override_tag}{text}"
    return f"Dialogue: 0,{format_ass_time(start)},{format_ass_time(end)},{style_name},,0,0,0,,{text}"
