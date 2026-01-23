"""Export endpoints for subtitles and rendered video."""

from typing import Any

from fastapi import APIRouter, Form, HTTPException, Request
from fastapi.responses import FileResponse, RedirectResponse

from app.config import OUTPUTS_DIR, UPLOADS_DIR
from app.services.cleanup import touch_job
from app.services.jobs import create_job, find_active_job, load_job, touch_job_access, update_job
from app.services.subtitles import load_subtitle_job, subtitles_to_srt, subtitles_to_vtt

router = APIRouter()


def _require_user(request: Request):
    user = getattr(request.state, "user", None)
    if not user:
        return None
    return user


def _ensure_owner(job_id: str, user_id: int) -> bool:
    job_record = load_job(job_id)
    if not job_record:
        raise HTTPException(status_code=404, detail="Project not found")
    if job_record.get("owner_user_id") is None:
        update_job(job_id, {"owner_user_id": int(user_id)})
        job_record["owner_user_id"] = int(user_id)
    return job_record.get("owner_user_id") == int(user_id)


@router.post("/export/{job_id}/subtitles")
def export_subtitles(request: Request, job_id: str, format: str = Form("srt")) -> Any:
    """Export subtitles in SRT or VTT format."""
    user = _require_user(request)
    if not user:
        return RedirectResponse(url="/login", status_code=303)
    if not _ensure_owner(job_id, user["id"]):
        raise HTTPException(status_code=403, detail="Access denied")
    job_data = load_subtitle_job(job_id)
    if not job_data:
        raise HTTPException(status_code=404, detail="Subtitle job not found")
    touch_job_access(job_id)

    format = format.lower().strip()
    if format not in {"srt", "vtt"}:
        raise HTTPException(status_code=400, detail="Unsupported subtitle format")

    subtitles = job_data.get("subtitles", [])
    output_path = OUTPUTS_DIR / f"{job_id}.{format}"
    touch_job(job_id)

    if format == "srt":
        output_path.write_text(subtitles_to_srt(subtitles), encoding="utf-8")
        media_type = "text/plain"
    else:
        output_path.write_text(subtitles_to_vtt(subtitles), encoding="utf-8")
        media_type = "text/vtt"

    filename = f"{job_id}.{format}"
    return FileResponse(path=str(output_path), media_type=media_type, filename=filename)


@router.post("/export/{job_id}/video")
def export_video(request: Request, job_id: str) -> Any:
    """Export a video with burned-in subtitles."""
    user = _require_user(request)
    if not user:
        return RedirectResponse(url="/login", status_code=303)
    if not _ensure_owner(job_id, user["id"]):
        raise HTTPException(status_code=403, detail="Access denied")
    job_data = load_subtitle_job(job_id)
    if not job_data:
        raise HTTPException(status_code=404, detail="Subtitle job not found")
    touch_job_access(job_id)

    existing = find_active_job(
        "export",
        lambda job: job.get("input", {}).get("options", {}).get("subtitle_job_id") == job_id,
    )
    if existing:
        return {"job_id": existing.get("job_id"), "status": existing.get("status")}

    session_id = getattr(request.state, "session_id", None)
    export_job = create_job(
        "export",
        {"video_path": str(UPLOADS_DIR / job_data.get("video_filename", "")), "options": {"subtitle_job_id": job_id}},
        owner_session_id=session_id,
        owner_user_id=user["id"],
    )
    return {"job_id": export_job["job_id"], "status": export_job["status"]}


@router.post("/export/{job_id}/video-karaoke")
def export_video_karaoke(request: Request, job_id: str) -> Any:
    """Export a video with burned-in karaoke word highlighting."""
    user = _require_user(request)
    if not user:
        return RedirectResponse(url="/login", status_code=303)
    if not _ensure_owner(job_id, user["id"]):
        raise HTTPException(status_code=403, detail="Access denied")
    job_data = load_subtitle_job(job_id)
    if not job_data:
        raise HTTPException(status_code=404, detail="Subtitle job not found")

    existing = find_active_job(
        "karaoke_export",
        lambda job: job.get("input", {}).get("options", {}).get("subtitle_job_id") == job_id,
    )
    if existing:
        return {"job_id": existing.get("job_id"), "status": existing.get("status")}

    session_id = getattr(request.state, "session_id", None)
    export_job = create_job(
        "karaoke_export",
        {"video_path": str(UPLOADS_DIR / job_data.get("video_filename", "")), "options": {"subtitle_job_id": job_id}},
        owner_session_id=session_id,
        owner_user_id=user["id"],
    )
    return {"job_id": export_job["job_id"], "status": export_job["status"]}
