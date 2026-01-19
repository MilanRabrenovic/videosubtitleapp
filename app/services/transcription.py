"""Speech-to-text orchestration using Whisper."""

import subprocess
import tempfile
from pathlib import Path
from typing import Dict, List

import whisper


def extract_audio(video_path: Path) -> Path:
    """Extract mono 16kHz WAV audio from a video file using FFmpeg."""
    temp_file = tempfile.NamedTemporaryFile(suffix=".wav", delete=False)
    temp_path = Path(temp_file.name)
    temp_file.close()

    command = [
        "ffmpeg",
        "-y",
        "-i",
        str(video_path),
        "-ac",
        "1",
        "-ar",
        "16000",
        "-vn",
        str(temp_path),
    ]
    subprocess.run(command, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    return temp_path


def transcribe_video(video_path: Path, model_name: str = "base") -> List[Dict[str, str]]:
    """Transcribe a video file and return Whisper segments."""
    model = whisper.load_model(model_name)
    audio_path = extract_audio(video_path)
    try:
        result = model.transcribe(str(audio_path), fp16=False)
    finally:
        audio_path.unlink(missing_ok=True)

    segments: List[Dict[str, str]] = []
    for segment in result.get("segments", []):
        segments.append(
            {
                "start": segment["start"],
                "end": segment["end"],
                "text": segment["text"].strip(),
            }
        )
    return segments
