"""Job status endpoints."""

from pathlib import Path
from typing import Any, Dict

from fastapi import APIRouter, HTTPException

from app.config import OUTPUTS_DIR
from app.services.jobs import load_job

router = APIRouter()


def _output_url(path_value: str | None) -> str | None:
    if not path_value:
        return None
    try:
        path = OUTPUTS_DIR / Path(path_value).name
    except Exception:
        return None
    if path.exists():
        return f"/outputs/{path.name}"
    return None


@router.get("/jobs/{job_id}")
def job_status(job_id: str) -> Dict[str, Any]:
    job = load_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    output = job.get("output") or {}
    return {
        "job_id": job.get("job_id"),
        "type": job.get("type"),
        "status": job.get("status"),
        "error": job.get("error"),
        "output": {
            "subtitle_path": output.get("subtitle_path"),
            "video_path": output.get("video_path"),
            "video_url": _output_url(output.get("video_path")),
        },
    }
