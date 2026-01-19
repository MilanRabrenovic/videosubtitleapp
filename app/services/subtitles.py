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
