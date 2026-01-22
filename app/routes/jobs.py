"""Job status endpoints."""

from pathlib import Path
from typing import Any, Dict

from fastapi import APIRouter, Form, HTTPException, Request

from app.config import OUTPUTS_DIR
from app.services.jobs import delete_job, last_failed_step, list_recent_jobs, load_job, touch_job_access, update_job

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
        "failed_step": last_failed_step(job),
        "last_accessed_at": job.get("last_accessed_at"),
        "pinned": job.get("pinned"),
        "locked": job.get("locked"),
        "expires_at": job.get("expires_at"),
        "output": {
            "subtitle_path": output.get("subtitle_path"),
            "video_path": output.get("video_path"),
            "video_url": _output_url(output.get("video_path")),
            "download_name": output.get("download_name"),
        },
    }


@router.get("/jobs/recent")
def recent_jobs(request: Request) -> Dict[str, Any]:
    session_id = getattr(request.state, "session_id", None)
    jobs = []
    for job in list_recent_jobs(owner_session_id=session_id):
        jobs.append(
            {
                "job_id": job.get("job_id"),
                "type": job.get("type"),
                "status": job.get("status"),
                "last_accessed_at": job.get("last_accessed_at"),
                "title": (job.get("input", {}) or {}).get("options", {}).get("title"),
            }
        )
    return {"jobs": jobs}


@router.get("/jobs/mine")
def my_jobs(request: Request) -> Dict[str, Any]:
    session_id = getattr(request.state, "session_id", None)
    jobs = []
    for job in list_recent_jobs(owner_session_id=session_id):
        jobs.append(
            {
                "job_id": job.get("job_id"),
                "type": job.get("type"),
                "status": job.get("status"),
                "last_accessed_at": job.get("last_accessed_at"),
            }
        )
    return {"jobs": jobs}


@router.post("/jobs/{job_id}/pin")
def pin_job(job_id: str, pinned: str = Form("off")) -> Dict[str, Any]:
    job = load_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    update_job(job_id, {"pinned": pinned == "on"})
    touch_job_access(job_id)
    return {"job_id": job_id, "pinned": pinned == "on"}


@router.post("/jobs/{job_id}/touch")
def touch_job(job_id: str, locked: str = Form(None)) -> Dict[str, Any]:
    job = load_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    lock_value = None
    if locked is not None:
        lock_value = locked == "on"
    updated = touch_job_access(job_id, lock_value)
    return {
        "job_id": job_id,
        "last_accessed_at": updated.get("last_accessed_at") if updated else None,
        "locked": updated.get("locked") if updated else None,
    }


@router.post("/jobs/{job_id}/delete")
def delete_job_route(job_id: str) -> Dict[str, Any]:
    job = load_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    if job.get("locked"):
        raise HTTPException(status_code=409, detail="Job is locked")
    if not delete_job(job_id):
        raise HTTPException(status_code=400, detail="Unable to delete job")
    return {"job_id": job_id, "deleted": True}
