"""Job status endpoints."""

from pathlib import Path
from typing import Any, Dict

from fastapi import APIRouter, Form, HTTPException, Request

from app.config import OUTPUTS_DIR
from app.services.jobs import delete_job, last_failed_step, list_recent_jobs, load_job, touch_job_access, update_job

router = APIRouter()


def _require_user(request: Request):
    user = getattr(request.state, "user", None)
    if not user:
        raise HTTPException(status_code=401, detail="Authentication required")
    return user


def _ensure_owner(job_id: str, user_id: int) -> dict:
    job = load_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Project not found")
    if job.get("owner_user_id") is None:
        update_job(job_id, {"owner_user_id": int(user_id)})
        job["owner_user_id"] = int(user_id)
    if job.get("owner_user_id") != int(user_id):
        raise HTTPException(status_code=403, detail="Access denied")
    return job


def _output_url(job_id: str, path_value: str | None) -> str | None:
    if not path_value:
        return None
    try:
        path = OUTPUTS_DIR / Path(path_value).name
    except Exception:
        return None
    if path.exists():
        return f"/media/outputs/{job_id}/{path.name}"
    return None


@router.get("/jobs/{job_id}")
def job_status(request: Request, job_id: str) -> Dict[str, Any]:
    user = _require_user(request)
    job = _ensure_owner(job_id, user["id"])
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
            "video_url": _output_url(job_id, output.get("video_path")),
            "download_name": output.get("download_name"),
        },
    }


@router.get("/jobs/recent")
def recent_jobs(request: Request) -> Dict[str, Any]:
    user = _require_user(request)
    session_id = getattr(request.state, "session_id", None)
    jobs = []
    for job in list_recent_jobs(owner_user_id=user["id"], owner_session_id=session_id):
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
    user = _require_user(request)
    session_id = getattr(request.state, "session_id", None)
    jobs = []
    for job in list_recent_jobs(owner_user_id=user["id"], owner_session_id=session_id):
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
def pin_job(request: Request, job_id: str, pinned: str = Form("off")) -> Dict[str, Any]:
    user = _require_user(request)
    _ensure_owner(job_id, user["id"])
    update_job(job_id, {"pinned": pinned == "on"})
    touch_job_access(job_id)
    return {"job_id": job_id, "pinned": pinned == "on"}


@router.post("/jobs/{job_id}/touch")
def touch_job(request: Request, job_id: str, locked: str = Form(None)) -> Dict[str, Any]:
    user = _require_user(request)
    _ensure_owner(job_id, user["id"])
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
def delete_job_route(request: Request, job_id: str) -> Dict[str, Any]:
    user = _require_user(request)
    job = _ensure_owner(job_id, user["id"])
    if job.get("locked"):
        raise HTTPException(status_code=409, detail="Job is locked")
    if not delete_job(job_id):
        raise HTTPException(status_code=400, detail="Unable to delete job")
    return {"job_id": job_id, "deleted": True}
