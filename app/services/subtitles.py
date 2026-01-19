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


def generate_karaoke_ass(words: List[Dict[str, Any]], output_path: Path) -> None:
    """Generate an ASS file with karaoke word highlighting."""
    header = "\n".join(
        [
            "[Script Info]",
            "ScriptType: v4.00+",
            "PlayResX: 1920",
            "PlayResY: 1080",
            "",
            "[V4+ Styles]",
            "Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, "
            "Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, "
            "MarginR, MarginV, Encoding",
            "Style: Default,Arial,48,&H00FFFFFF,&H00FFFFFF,&H00000000,&H00000000,1,0,0,0,100,100,0,0,1,2,0,2,80,80,50,1",
            "",
            "[Events]",
            "Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text",
        ]
    )

    def format_ass_time(seconds: float) -> str:
        total_cs = max(0, int(round(seconds * 100)))
        hours, remainder = divmod(total_cs, 3600 * 100)
        minutes, remainder = divmod(remainder, 60 * 100)
        secs, cs = divmod(remainder, 100)
        return f"{hours}:{minutes:02}:{secs:02}.{cs:02}"

    def escape_ass_text(text: str) -> str:
        return text.replace("\\", "\\\\").replace("{", "\\{").replace("}", "\\}")

    lines: List[str] = [header]
    line_words: List[Dict[str, Any]] = []
    for word in words:
        word_text = str(word.get("word", "")).strip()
        if not word_text:
            continue
        line_words.append(word)
        if word_text.endswith((".", "?", "!")):
            lines.append(_build_ass_dialogue(line_words, format_ass_time, escape_ass_text))
            line_words = []

    if line_words:
        lines.append(_build_ass_dialogue(line_words, format_ass_time, escape_ass_text))

    output_path.write_text("\n".join(lines).strip() + "\n", encoding="utf-8")


def build_karaoke_words(words: List[Dict[str, Any]], subtitles: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Align word timings to subtitle text, falling back to even timing when counts mismatch."""
    if not subtitles:
        return words

    def parse_timestamp(value: str) -> float:
        try:
            time_part, ms_part = value.split(",")
            hours, minutes, seconds = time_part.split(":")
            return int(hours) * 3600 + int(minutes) * 60 + int(seconds) + int(ms_part) / 1000.0
        except ValueError:
            return 0.0

    aligned_words: List[Dict[str, Any]] = []
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
        if block_words and len(block_words) == len(tokens):
            for token, word in zip(tokens, block_words):
                aligned_words.append(
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
                aligned_words.append({"word": token, "start": start, "end": end})

    return aligned_words


def _build_ass_dialogue(
    words: List[Dict[str, Any]],
    format_ass_time,
    escape_ass_text,
) -> str:
    start = float(words[0].get("start", 0.0))
    end = float(words[-1].get("end", start))
    line_start_ms = start * 1000.0
    chunks: List[str] = []
    for word in words:
        word_text = escape_ass_text(str(word.get("word", "")).strip())
        word_start = float(word.get("start", start))
        word_end = float(word.get("end", word_start))
        duration = max(1, int(round((word_end - word_start) * 100)))
        rel_start = max(0, int(round((word_start - start) * 1000)))
        rel_end = max(rel_start + 1, int(round((word_end - start) * 1000)))
        if rel_start == 0:
            chunks.append(
                f"{{\\k{duration}\\c&H0000FFFF&\\t({rel_end},{rel_end},\\c&H00FFFFFF&)}}{word_text} "
            )
        else:
            chunks.append(
                f"{{\\k{duration}\\c&H00FFFFFF&\\t({rel_start},{rel_start},\\c&H0000FFFF&)\\t({rel_end},{rel_end},\\c&H00FFFFFF&)}}"
                f"{word_text} "
            )
    text = "".join(chunks).strip()
    return f"Dialogue: 0,{format_ass_time(start)},{format_ass_time(end)},Default,,0,0,0,,{text}"
