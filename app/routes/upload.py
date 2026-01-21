"""Upload endpoints for new video jobs."""

import uuid
from pathlib import Path
from typing import Any

from fastapi import APIRouter, File, Form, HTTPException, Request, UploadFile
from fastapi.responses import RedirectResponse
from fastapi.templating import Jinja2Templates

from app.config import (
    ALLOWED_VIDEO_EXTENSIONS,
    MAX_STORAGE_BYTES,
    MAX_UPLOAD_BYTES,
    MAX_VIDEO_SECONDS,
    OUTPUTS_DIR,
    TEMPLATES_DIR,
    UPLOADS_DIR,
)
from app.services.cleanup import cleanup_storage
from app.services.jobs import create_job
from app.services.video import validate_video_file

router = APIRouter()
templates = Jinja2Templates(directory=str(TEMPLATES_DIR))


@router.get("/upload")
def upload_form(request: Request) -> Any:
    """Render the upload form."""
    return templates.TemplateResponse("upload.html", {"request": request})


@router.post("/upload")
def handle_upload(
    request: Request,
    video: UploadFile = File(...),
    title: str = Form(""),
    language: str = Form(""),
) -> Any:
    """Accept an uploaded video and create a subtitle job."""
    job_id = uuid.uuid4().hex
    extension = Path(video.filename).suffix.lower()
    if extension not in ALLOWED_VIDEO_EXTENSIONS:
        raise HTTPException(status_code=400, detail="Unsupported video format")
    safe_name = f"{job_id}_{Path(video.filename).name}"
    upload_path = UPLOADS_DIR / safe_name

    with upload_path.open("wb") as handle:
        while True:
            chunk = video.file.read(1024 * 1024)
            if not chunk:
                break
            handle.write(chunk)
    cleanup_storage(MAX_STORAGE_BYTES)

    try:
        validate_video_file(upload_path, MAX_UPLOAD_BYTES, MAX_VIDEO_SECONDS)
    except ValueError as exc:
        upload_path.unlink(missing_ok=True)
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    job_input = {
        "video_path": str(upload_path),
        "options": {
            "title": title.strip() or video.filename,
            "video_filename": safe_name,
            "language": language.strip().lower() or None,
        },
    }
    create_job("transcription", job_input, job_id=job_id)

    return RedirectResponse(url=f"/edit/{job_id}", status_code=303)
