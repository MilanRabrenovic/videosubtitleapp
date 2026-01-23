"""Protected media endpoints for uploads/outputs."""

from pathlib import Path
from typing import Any

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import FileResponse

from app.config import OUTPUTS_DIR, UPLOADS_DIR
from app.services.jobs import load_job, update_job

router = APIRouter()


def _require_owner(job_id: str, request: Request) -> dict:
    user = getattr(request.state, "user", None)
    if not user:
        raise HTTPException(status_code=401, detail="Authentication required")
    job = load_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Project not found")
    if job.get("owner_user_id") is None:
        update_job(job_id, {"owner_user_id": int(user["id"])})
    if job.get("owner_user_id") != int(user["id"]):
        raise HTTPException(status_code=403, detail="Access denied")
    return job


@router.get("/media/outputs/{job_id}/{filename}")
def output_media(job_id: str, filename: str, request: Request) -> Any:
    _require_owner(job_id, request)
    path = OUTPUTS_DIR / Path(filename).name
    if not path.exists():
        raise HTTPException(status_code=404, detail="File not found")
    return FileResponse(path)


@router.get("/media/uploads/{job_id}/{filename}")
def upload_media(job_id: str, filename: str, request: Request) -> Any:
    _require_owner(job_id, request)
    path = UPLOADS_DIR / Path(filename).name
    if not path.exists():
        raise HTTPException(status_code=404, detail="File not found")
    return FileResponse(path)
