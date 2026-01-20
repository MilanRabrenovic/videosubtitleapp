"""Video processing helpers (FFmpeg integration)."""

import subprocess
from pathlib import Path


def _escape_filter_path(path: Path) -> str:
    """Escape a file path for FFmpeg filter arguments."""
    escaped = str(path).replace("\\", "\\\\")
    escaped = escaped.replace(":", "\\:")
    escaped = escaped.replace(",", "\\,")
    return escaped


def get_video_dimensions(video_path: Path) -> tuple[int, int]:
    """Return the source video's width/height using ffprobe."""
    command = [
        "ffprobe",
        "-v",
        "error",
        "-select_streams",
        "v:0",
        "-show_entries",
        "stream=width,height",
        "-of",
        "csv=p=0:s=x",
        str(video_path),
    ]
    result = subprocess.run(command, capture_output=True, text=True)
    if result.returncode != 0:
        return 1920, 1080
    output = result.stdout.strip()
    try:
        width_str, height_str = output.split("x")
        return int(width_str), int(height_str)
    except ValueError:
        return 1920, 1080


def burn_in_subtitles(video_path: Path, subtitles_path: Path, output_path: Path) -> None:
    """Burn subtitles into a video using FFmpeg."""
    filter_arg = f"subtitles=filename={_escape_filter_path(subtitles_path)}"
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


def burn_in_ass(video_path: Path, ass_path: Path, output_path: Path, fonts_dir: Path | None = None) -> None:
    """Burn ASS subtitles into a video using FFmpeg."""
    filter_arg = f"ass=filename={_escape_filter_path(ass_path)}"
    if fonts_dir:
        filter_arg = f"{filter_arg}:fontsdir={_escape_filter_path(fonts_dir)}"
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
