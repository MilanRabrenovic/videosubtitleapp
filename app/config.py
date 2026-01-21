"""App configuration and filesystem paths."""

from pathlib import Path

# Base directory is the project root (subtitle-app).
BASE_DIR = Path(__file__).resolve().parents[1]

UPLOADS_DIR = BASE_DIR / "uploads"
OUTPUTS_DIR = BASE_DIR / "outputs"
FONTS_DIR = OUTPUTS_DIR / "fonts"
JOBS_DIR = BASE_DIR / "jobs"
TEMPLATES_DIR = BASE_DIR / "app" / "templates"
STATIC_DIR = BASE_DIR / "app" / "static"
MAX_STORAGE_BYTES = 20 * 1024 * 1024 * 1024
MAX_UPLOAD_BYTES = 500 * 1024 * 1024
MAX_VIDEO_SECONDS = 15 * 60
ALLOWED_VIDEO_EXTENSIONS = {".mp4", ".mov", ".mkv", ".webm", ".m4v"}
JOB_WORKER_COUNT = 1
JOB_MAX_AGE_HOURS = 72


def ensure_directories() -> None:
    """Create required directories if they do not exist."""
    UPLOADS_DIR.mkdir(parents=True, exist_ok=True)
    OUTPUTS_DIR.mkdir(parents=True, exist_ok=True)
    FONTS_DIR.mkdir(parents=True, exist_ok=True)
    JOBS_DIR.mkdir(parents=True, exist_ok=True)
