"""Speech-to-text orchestration using Whisper."""

import subprocess
import tempfile
from pathlib import Path
from typing import Dict, List, Tuple, Union

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


def transcribe_video(
    video_path: Path, model_name: str = "base", language: str | None = None
) -> Tuple[List[Dict[str, str]], List[Dict[str, Union[str, float]]]]:
    """Transcribe a video file and return Whisper segments and word timings."""
    model = whisper.load_model(model_name)
    audio_path = extract_audio(video_path)
    try:
        result = model.transcribe(
            str(audio_path), fp16=False, word_timestamps=True, language=language
        )
    finally:
        audio_path.unlink(missing_ok=True)

    segments: List[Dict[str, str]] = []
    words: List[Dict[str, float]] = []
    for segment in result.get("segments", []):
        segments.append(
            {
                "start": segment["start"],
                "end": segment["end"],
                "text": segment["text"].strip(),
            }
        )
        for word in segment.get("words", []):
            word_text = str(word.get("word", "")).strip()
            if not word_text:
                continue
            words.append(
                {
                    "word": word_text,
                    "start": float(word.get("start", segment["start"])),
                    "end": float(word.get("end", segment["end"])),
                }
            )
    return segments, words
