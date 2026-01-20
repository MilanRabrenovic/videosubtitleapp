"""Subtitle storage and format conversion helpers."""

import json
import re
from pathlib import Path
from typing import Any, Dict, List, Optional

from app.config import OUTPUTS_DIR


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


def default_style() -> Dict[str, Any]:
    """Return default subtitle styling values."""
    return {
        "font_family": "Arial",
        "font_size": 48,
        "font_bold": True,
        "font_italic": False,
        "text_color": "#FFFFFF",
        "highlight_color": "#FFFF00",
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
        chunks = [line_words[i : i + max_words] for i in range(0, len(line_words), max_words)]
        for chunk in chunks:
            if not chunk:
                continue
            start = float(chunk[0].get("start", 0.0))
            end = float(chunk[-1].get("end", start))
            if start < last_end + min_gap:
                start = last_end + min_gap
            if end < start + min_gap:
                end = start + min_gap
            text = " ".join(str(word.get("word", "")).strip() for word in chunk).strip()
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
    background_enabled = bool(style.get("background_enabled"))
    background_opacity = float(style.get("background_opacity", 0.6))
    background_opacity = min(max(background_opacity, 0.0), 1.0)
    back_alpha = int(round((1.0 - background_opacity) * 255))
    alignment = {"bottom": 2, "center": 5, "top": 8}.get(style.get("position"), 2)
    margin_v = int(style.get("margin_v", 50))
    outline_value = int(style.get("outline_size", 2))
    bold_flag = -1 if style.get("font_bold", True) else 0
    italic_flag = -1 if style.get("font_italic", False) else 0
    primary = _ass_color(str(style.get("text_color", "#FFFFFF")), 0)
    secondary = _ass_color(str(style.get("text_color", "#FFFFFF")), 0)
    back_color = _ass_color(str(style.get("background_color", "#000000")), back_alpha)
    outline = _ass_color(str(style.get("outline_color", "#000000")), 0)
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
    return " ".join(text.replace("\r", " ").replace("\n", " ").split())


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
    side_padding = 15
    font_size = int(style.get("font_size", 48))
    outline = int(style.get("outline_size", 0)) if style.get("outline_enabled") else 0
    background_padding = int(style.get("background_padding", 0)) if style.get("background_enabled") else 0
    safe_width = play_res_x - (side_padding * 2) - (background_padding * 2) - (outline * 2)
    char_width = max(1.0, font_size * 0.72)
    return max(10, int(safe_width / char_width))


def _split_text_lines(text: str, style: Dict[str, Any]) -> List[str]:
    """Split text into lines by max words and estimated max characters."""
    if style.get("single_line", True):
        return [text]
    max_words = int(style.get("max_words_per_line", 7))
    max_chars = _max_chars_per_line(style)
    segments = [segment for segment in text.replace("\r", "").split("\n") if segment.strip()]
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
) -> List[str]:
    """Create extra dialogue lines for sup/sub overlays."""
    if not overlays or not base_text:
        return []
    font_size = int(style.get("font_size", 48))
    small_size = max(8, int(round(font_size * 0.6)))
    alignment = pos["alignment"]
    if alignment == 2:
        top_y = pos["y"] - font_size
        bottom_y = pos["y"]
    elif alignment == 8:
        top_y = pos["y"]
        bottom_y = pos["y"] + font_size
    else:
        top_y = pos["y"] - (font_size / 2.0)
        bottom_y = pos["y"] + (font_size / 2.0)
    sup_y = top_y - (font_size * 0.02)
    sub_y = bottom_y + (font_size * 0.010)
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
        tag = f"{{\\an{alignment}\\pos({pos['x']},{int(round(overlay_y))})}}"
        overlay_line = (
            f"{{\\alpha&HFF&}}{prefix_text}"
            f"{{\\alpha&H00&}}{{\\fs{small_size}}}{ass_text}{{\\fs{font_size}}}"
            f"{{\\alpha&HFF&}}{suffix_text}{{\\alpha&H00&}}"
        )
        dialogues.append(
            f"Dialogue: 0,{format_ass_time(start)},{format_ass_time(end)},Default,,0,0,0,,{tag}{overlay_line}"
        )
    return dialogues


def generate_karaoke_ass(
    word_lines: List[List[Dict[str, Any]]], output_path: Path, style: Optional[Dict[str, Any]] = None
) -> None:
    """Generate an ASS file with karaoke word highlighting."""
    style_data = normalize_style(style)
    header = _ass_header(style_data)
    highlight_color = _ass_color(str(style_data.get("highlight_color", "#FFFF00")), 0)
    base_color = _ass_color(str(style_data.get("text_color", "#FFFFFF")), 0)

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
            plain_text = " ".join(str(word.get("word", "")).strip() for word in chunk_words).strip()
            layout = _sup_sub_layout(plain_text, style_data)
            base_text = layout["base_text"]
            render_text = layout["render_text"]
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
                )
            if style_data.get("background_enabled"):
                lines.append(
                    f"Dialogue: 0,{format_ass_time(block_start)},"
                    f"{format_ass_time(block_end)},"
                    f"Box,,0,0,0,,{blur_tag}{pos_tag}{_escape_ass_text(base_text)}"
                )
            karaoke_style = style_data.copy()
            karaoke_style["single_line"] = True
            dialogue = _build_ass_dialogue(
                chunk_words,
                format_ass_time,
                _format_word_with_alpha,
                base_color,
                highlight_color,
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

def build_karaoke_lines(words: List[Dict[str, Any]], subtitles: List[Dict[str, Any]]) -> List[List[Dict[str, Any]]]:
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

        tokens = block_text.split()
        if not tokens:
            continue
        line_words: List[Dict[str, Any]] = []
        if block_words and len(block_words) == len(tokens):
            for token, word in zip(tokens, block_words):
                line_words.append(
                    {
                        "word": token,
                        "start": float(word.get("start", block_start)),
                        "end": float(word.get("end", block_start)),
                    }
                )
        else:
            block_duration = max(0.1, block_end - block_start)
            per_word = block_duration / len(tokens)
            for offset, token in enumerate(tokens):
                start = block_start + offset * per_word
                end = start + per_word
                line_words.append({"word": token, "start": start, "end": end})
        if line_words:
            line_words = _smooth_word_timings(line_words, block_start, block_end)
            line_words[0]["_line_start"] = block_start
            line_words[-1]["_line_end"] = block_end
            aligned_lines.append(line_words)

    return aligned_lines


def _smooth_word_timings(
    line_words: List[Dict[str, Any]],
    line_start: float,
    line_end: float,
    min_duration: float = 0.04,
    max_duration: float = 0.6,
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
        if duration > max_duration:
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
    subtitles: List[Dict[str, Any]], words: Optional[List[Dict[str, Any]]]
) -> tuple[List[Dict[str, Any]], List[List[Dict[str, Any]]]]:
    """Apply manual line breaks and return updated subtitles and karaoke lines."""
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
            if line_words:
                new_lines.append(line_words)
            group_counter += 1
            continue

        tokens_per_segment = [segment.split() for segment in segments]
        total_tokens = sum(len(tokens) for tokens in tokens_per_segment)
        block_start = srt_timestamp_to_seconds(str(block.get("start", "00:00:00,000")))
        block_end = srt_timestamp_to_seconds(str(block.get("end", "00:00:00,000")))
        if block_end <= block_start:
            continue

        if line_words and total_tokens == len(line_words):
            cursor = 0
            for tokens in tokens_per_segment:
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
                        "text": " ".join(tokens),
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
            for seg_index, tokens in enumerate(tokens_per_segment):
                if not tokens:
                    continue
                weight = len(tokens) / total_tokens
                segment_duration = block_duration * weight
                start = current_time
                end = block_end if seg_index == len(tokens_per_segment) - 1 else start + segment_duration
                current_time = end
                per_word = max(0.05, (end - start) / len(tokens))
                segment_words = []
                for token_index, token in enumerate(tokens):
                    w_start = start + token_index * per_word
                    w_end = w_start + per_word
                    segment_words.append({"word": token, "start": w_start, "end": w_end})
                new_subtitles.append(
                    {
                        "start": format_timestamp(start),
                        "end": format_timestamp(end),
                        "text": " ".join(tokens),
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
    style_data: Dict[str, Any],
    style_name: str,
    override_tag: str = "",
) -> str:
    start = float(words[0].get("_line_start", words[0].get("start", 0.0)))
    end = float(words[-1].get("_line_end", words[-1].get("end", start)))
    chunks: List[str] = []
    for word in words:
        word_text = format_ass_text(str(word.get("word", "")).strip(), style_data)
        word_start = float(word.get("start", start))
        word_end = float(word.get("end", word_start))
        if word_start < start:
            word_start = start
        if word_end > end:
            word_end = end
        duration = max(1, int(round((word_end - word_start) * 100)))
        rel_start = max(0, int(round((word_start - start) * 1000)))
        rel_end = max(rel_start + 1, int(round((word_end - start) * 1000)))
        if rel_start == 0:
            chunks.append(
                f"{{\\k{duration}\\1c{highlight_color}&\\t({rel_end},{rel_end},\\1c{base_color}&)}}{word_text} "
            )
        else:
            chunks.append(
                f"{{\\k{duration}\\1c{base_color}&"
                f"\\t({rel_start},{rel_start},\\1c{highlight_color}&)"
                f"\\t({rel_end},{rel_end},\\1c{base_color}&)}}{word_text} "
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
