"""Subtitle storage and format conversion helpers."""

import json
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
        "text_color": "#FFFFFF",
        "highlight_color": "#FFFF00",
        "outline_color": "#000000",
        "background_enabled": False,
        "background_opacity": 0.6,
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
    min_gap = 0.02
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
    """Build the ASS header with a single default style."""
    style = normalize_style(style)
    background_enabled = bool(style.get("background_enabled"))
    background_opacity = float(style.get("background_opacity", 0.6))
    background_opacity = min(max(background_opacity, 0.0), 1.0)
    back_alpha = int(round((1.0 - background_opacity) * 255))
    border_style = 3 if background_enabled else 1
    alignment = {"bottom": 2, "center": 5, "top": 8}.get(style.get("position"), 2)
    margin_v = int(style.get("margin_v", 50))
    primary = _ass_color(str(style.get("text_color", "#FFFFFF")), 0)
    secondary = _ass_color(str(style.get("text_color", "#FFFFFF")), 0)
    outline = _ass_color(str(style.get("outline_color", "#000000")), 0)
    back = _ass_color("#000000", back_alpha)

    wrap_style = "2" if style.get("single_line", True) else "0"
    return "\n".join(
        [
            "[Script Info]",
            "ScriptType: v4.00+",
            f"WrapStyle: {wrap_style}",
            "PlayResX: 1920",
            "PlayResY: 1080",
            "",
            "[V4+ Styles]",
            "Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, "
            "Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, "
            "MarginR, MarginV, Encoding",
            (
                "Style: Default,"
                f"{style.get('font_family', 'Arial')},{int(style.get('font_size', 48))},"
                f"{primary},{secondary},{outline},{back},"
                "1,0,0,0,100,100,0,0,"
                f"{border_style},2,0,{alignment},80,80,{margin_v},1"
            ),
            "",
            "[Events]",
            "Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text",
        ]
    )


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


def _wrap_text(text: str, style: Dict[str, Any]) -> str:
    """Wrap text by max words per line when single-line is disabled."""
    if style.get("single_line", True):
        return text
    max_words = int(style.get("max_words_per_line", 7))
    if max_words <= 0:
        return text
    words = text.split()
    lines: List[str] = []
    for index in range(0, len(words), max_words):
        lines.append(" ".join(words[index : index + max_words]))
    return "\\N".join(lines)


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

    def escape_ass_text(text: str) -> str:
        return text.replace("\\", "\\\\").replace("{", "\\{").replace("}", "\\}")

    lines: List[str] = [header]
    for line_words in word_lines:
        if not line_words:
            continue
        lines.append(
            _build_ass_dialogue(line_words, format_ass_time, escape_ass_text, base_color, highlight_color, style_data)
        )

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

    def escape_ass_text(text: str) -> str:
        return text.replace("\\", "\\\\").replace("{", "\\{").replace("}", "\\}")

    for block in subtitles:
        start = srt_timestamp_to_seconds(str(block.get("start", "00:00:00,000")))
        end = srt_timestamp_to_seconds(str(block.get("end", "00:00:00,000")))
        if end <= start:
            continue
        text = escape_ass_text(str(block.get("text", "")).strip())
        if style_data.get("single_line", True):
            text = _single_line_text(text, style_data)
            text = _apply_single_line_override(text, style_data)
        else:
            text = _wrap_text(text, style_data)
        if not text:
            continue
        lines.append(f"Dialogue: 0,{format_ass_time(start)},{format_ass_time(end)},Default,,0,0,0,,{text}")

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
            line_words[0]["_line_start"] = block_start
            line_words[-1]["_line_end"] = block_end
            aligned_lines.append(line_words)

    return aligned_lines


def _build_ass_dialogue(
    words: List[Dict[str, Any]],
    format_ass_time,
    escape_ass_text,
    base_color: str,
    highlight_color: str,
    style_data: Dict[str, Any],
) -> str:
    start = float(words[0].get("_line_start", words[0].get("start", 0.0)))
    end = float(words[-1].get("_line_end", words[-1].get("end", start)))
    chunks: List[str] = []
    for word in words:
        word_text = escape_ass_text(str(word.get("word", "")).strip())
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
        text = _wrap_text(text, style_data)
    return f"Dialogue: 0,{format_ass_time(start)},{format_ass_time(end)},Default,,0,0,0,,{text}"
