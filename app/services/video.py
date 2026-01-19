"""Video processing helpers (FFmpeg integration)."""

import subprocess
from pathlib import Path


def _escape_subtitles_path(path: Path) -> str:
    """Escape a subtitle path for the FFmpeg subtitles filter."""
    escaped = str(path).replace("\\", "\\\\")
    escaped = escaped.replace(":", "\\:")
    escaped = escaped.replace(",", "\\,")
    return escaped


def burn_in_subtitles(video_path: Path, subtitles_path: Path, output_path: Path) -> None:
    """Burn subtitles into a video using FFmpeg."""
    filter_arg = f"subtitles=filename={_escape_subtitles_path(subtitles_path)}"
    command = [
        "ffmpeg",
        "-y",
        "-i",
        str(video_path),
        "-vf",
        filter_arg,
        "-c:a",
        "copy",
        str(output_path),
    ]
    result = subprocess.run(command, capture_output=True, text=True)
    if result.returncode != 0:
        raise RuntimeError(f"FFmpeg failed: {result.stderr.strip()}")
