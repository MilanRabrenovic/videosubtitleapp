"""Video processing helpers (FFmpeg integration)."""

import subprocess
from pathlib import Path

from app.services.errors import JobError, error_payload

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
    try:
        result = subprocess.run(command, capture_output=True, text=True, timeout=10)
    except subprocess.TimeoutExpired:
        return 1920, 1080
    if result.returncode != 0:
        return 1920, 1080
    output = result.stdout.strip()
    try:
        width_str, height_str = output.split("x")
        return int(width_str), int(height_str)
    except ValueError:
        return 1920, 1080


def get_video_duration(video_path: Path) -> float | None:
    """Return video duration in seconds using ffprobe."""
    commands = [
        [
            "ffprobe",
            "-v",
            "error",
            "-show_entries",
            "format=duration",
            "-of",
            "default=nokey=1:noprint_wrappers=1",
            str(video_path),
        ],
        [
            "ffprobe",
            "-v",
            "error",
            "-select_streams",
            "v:0",
            "-show_entries",
            "stream=duration",
            "-of",
            "default=nokey=1:noprint_wrappers=1",
            str(video_path),
        ],
    ]
    for command in commands:
        try:
            result = subprocess.run(command, capture_output=True, text=True, timeout=10)
        except subprocess.TimeoutExpired:
            continue
        if result.returncode != 0:
            continue
        try:
            duration = float(result.stdout.strip())
        except ValueError:
            continue
        if duration > 0:
            return duration
    return None


def validate_video_file(video_path: Path, max_bytes: int, max_seconds: int) -> None:
    """Validate video file size and duration."""
    try:
        size = video_path.stat().st_size
    except OSError as exc:
        raise ValueError("Uploaded file is not accessible") from exc
    if size > max_bytes:
        raise ValueError("Video file is too large")
    duration = get_video_duration(video_path)
    if duration is not None and duration > max_seconds:
        raise ValueError("Video is too long")


def generate_waveform(video_path: Path, output_path: Path, width: int = 1200, height: int = 200) -> None:
    """Generate a waveform image for the video's audio track."""
    command = [
        "ffmpeg",
        "-y",
        "-i",
        str(video_path),
        "-filter_complex",
        f"showwavespic=s={width}x{height}:colors=0x1f2937",
        "-frames:v",
        "1",
        str(output_path),
    ]
    subprocess.run(command, capture_output=True, text=True, timeout=30)


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
    try:
        result = subprocess.run(command, capture_output=True, text=True, timeout=300)
    except subprocess.TimeoutExpired as exc:
        payload = error_payload(
            "TIMEOUT",
            "Video export timed out during subtitle rendering.",
            "Try a shorter video or reduce the output resolution.",
        )
        raise JobError(payload, str(exc)) from exc
    if result.returncode != 0:
        payload = _ffmpeg_error_payload(result.stderr)
        raise JobError(payload, result.stderr.strip())


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
    try:
        result = subprocess.run(command, capture_output=True, text=True, timeout=300)
    except subprocess.TimeoutExpired as exc:
        payload = error_payload(
            "TIMEOUT",
            "Video export timed out during subtitle rendering.",
            "Try a shorter video or reduce the output resolution.",
        )
        raise JobError(payload, str(exc)) from exc
    if result.returncode != 0:
        payload = _ffmpeg_error_payload(result.stderr)
        raise JobError(payload, result.stderr.strip())


def burn_in_ass_on_color(
    video_path: Path,
    ass_path: Path,
    output_path: Path,
    width: int,
    height: int,
    duration: float,
    fonts_dir: Path | None = None,
    color: str = "0x00FF00",
) -> None:
    """Render ASS subtitles over a solid-color background with original audio."""
    filter_arg = f"ass=filename={_escape_filter_path(ass_path)}"
    if fonts_dir:
        filter_arg = f"{filter_arg}:fontsdir={_escape_filter_path(fonts_dir)}"
    command = [
        "ffmpeg",
        "-y",
        "-f",
        "lavfi",
        "-i",
        f"color=c={color}:s={width}x{height}:d={duration}",
        "-i",
        str(video_path),
        "-vf",
        filter_arg,
        "-map",
        "0:v:0",
        "-map",
        "1:a:0?",
        "-c:v",
        "libx264",
        "-pix_fmt",
        "yuv420p",
        "-c:a",
        "copy",
        "-shortest",
        str(output_path),
    ]
    try:
        result = subprocess.run(command, capture_output=True, text=True, timeout=300)
    except subprocess.TimeoutExpired as exc:
        payload = error_payload(
            "TIMEOUT",
            "Video export timed out during subtitle rendering.",
            "Try a shorter video or reduce the output resolution.",
        )
        raise JobError(payload, str(exc)) from exc
    if result.returncode != 0:
        payload = _ffmpeg_error_payload(result.stderr)
        raise JobError(payload, result.stderr.strip())


def _ffmpeg_error_payload(stderr: str) -> dict:
    message = (stderr or "").lower()
    if "no such filter" in message or "subtitles" in message and "filter" in message:
        return error_payload(
            "FFMPEG_FAILED",
            "Video export failed because subtitle rendering is not supported.",
            "Install FFmpeg with libass support and try again.",
        )
    if "font" in message or "fonts" in message:
        return error_payload(
            "FFMPEG_FAILED",
            "Video export failed due to a font rendering issue.",
            "Try a different font or remove custom fonts.",
        )
    if "invalid data" in message or "unknown decoder" in message or "unsupported" in message:
        return error_payload(
            "INVALID_MEDIA",
            "We couldn't process this video format.",
            "Try a standard MP4 with H.264 video and AAC audio.",
        )
    return error_payload(
        "FFMPEG_FAILED",
        "Video export failed during subtitle rendering.",
        "Try a different font or reduce video resolution.",
    )
