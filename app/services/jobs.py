"""File-backed job queue for background processing."""

from __future__ import annotations

import json
import os
import threading
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path
from queue import Queue
from typing import Any, Callable, Dict, Iterable, Optional

from app.config import (
    JOB_QUEUE_NAME,
    JOBS_DIR,
    JOB_LOCK_TTL_MINUTES,
    JOB_MAX_AGE_HOURS,
    JOB_CLEANUP_BATCH,
    JOB_RECENT_LIMIT,
    JOB_RETENTION_DAYS,
    JOB_PINNED_RETENTION_DAYS,
    JOB_WORKER_COUNT,
    JOB_TIMEOUT_EXPORT,
    JOB_TIMEOUT_KARAOKE,
    JOB_TIMEOUT_PREVIEW,
    JOB_TIMEOUT_TRANSCRIBE,
    JOB_LOG_DIR,
    REDIS_URL,
)
from app.config import OUTPUTS_DIR

_queue: Queue[str] = Queue()
_queue_lock = threading.Lock()
_write_lock = threading.Lock()
_enqueued: set[str] = set()
_workers_started = False
_redis_queue = None
_redis_conn = None


def _redis_enabled() -> bool:
    return bool(REDIS_URL)


def _get_rq_queue():
    global _redis_queue, _redis_conn
    if _redis_queue is not None:
        return _redis_queue
    if not _redis_enabled():
        return None
    try:
        import redis
        from rq import Queue as RqQueue
    except Exception:
        return None
    _redis_conn = redis.from_url(REDIS_URL)
    _redis_queue = RqQueue(JOB_QUEUE_NAME, connection=_redis_conn)
    return _redis_queue


def _job_timeout(job: Dict[str, Any]) -> int | None:
    job_type = job.get("type")
    if job_type == "transcription":
        return JOB_TIMEOUT_TRANSCRIBE
    if job_type == "preview":
        return JOB_TIMEOUT_PREVIEW
    if job_type == "export":
        return JOB_TIMEOUT_EXPORT
    if job_type == "karaoke_export":
        return JOB_TIMEOUT_KARAOKE
    if job_type == "greenscreen_export":
        return JOB_TIMEOUT_EXPORT
    return None


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _now_iso() -> str:
    return _utcnow().isoformat(timespec="seconds").replace("+00:00", "Z")


def _parse_iso(value: Optional[str]) -> Optional[datetime]:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00")).astimezone(timezone.utc)
    except ValueError:
        return None


def _expires_at_iso(created_at: Optional[str]) -> str:
    created = _parse_iso(created_at) or _utcnow()
    return (created + timedelta(days=JOB_RETENTION_DAYS)).isoformat(timespec="seconds").replace("+00:00", "Z")


def _job_path(job_id: str) -> Path:
    return JOBS_DIR / f"{job_id}.json"


def _atomic_write(path: Path, payload: Dict[str, Any]) -> None:
    tmp_path = path.with_suffix(".tmp")
    with _write_lock:
        tmp_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
        os.replace(tmp_path, path)


def create_job(
    job_type: str,
    input_data: Dict[str, Any],
    job_id: Optional[str] = None,
    owner_session_id: Optional[str] = None,
    owner_user_id: Optional[int] = None,
) -> Dict[str, Any]:
    """Create a queued job and persist it."""
    job_id = job_id or uuid.uuid4().hex
    now = _now_iso()
    job = {
        "job_id": job_id,
        "type": job_type,
        "status": "queued",
        "progress": None,
        "error": None,
        "created_at": now,
        "updated_at": now,
        "last_accessed_at": now,
        "pinned": False,
        "locked": False,
        "expires_at": _expires_at_iso(now),
        "steps": [],
        "owner_session_id": owner_session_id,
        "owner_user_id": owner_user_id,
        "input": input_data,
        "output": {"subtitle_path": None, "video_path": None},
    }
    _atomic_write(_job_path(job_id), job)
    enqueue_job(job_id)
    return job


def load_job(job_id: str) -> Optional[Dict[str, Any]]:
    """Load a job from disk."""
    path = _job_path(job_id)
    if not path.exists():
        return None
    data = json.loads(path.read_text(encoding="utf-8"))
    changed = False
    if "last_accessed_at" not in data:
        data["last_accessed_at"] = data.get("updated_at") or data.get("created_at") or _now_iso()
        changed = True
    if "pinned" not in data:
        data["pinned"] = False
        changed = True
    if "locked" not in data:
        data["locked"] = False
        changed = True
    if "expires_at" not in data:
        data["expires_at"] = _expires_at_iso(data.get("created_at"))
        changed = True
    if "steps" not in data:
        data["steps"] = []
        changed = True
    if "owner_session_id" not in data:
        data["owner_session_id"] = None
        changed = True
    if "owner_user_id" not in data:
        data["owner_user_id"] = None
        changed = True
    if changed:
        _atomic_write(_job_path(job_id), data)
    return data


def update_job(job_id: str, updates: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """Update job fields and persist."""
    job = load_job(job_id)
    if not job:
        return None
    job.update(updates)
    job["updated_at"] = _now_iso()
    _atomic_write(_job_path(job_id), job)
    return job


def touch_job_access(job_id: str, locked: Optional[bool] = None) -> Optional[Dict[str, Any]]:
    """Update last_accessed_at and optionally lock state."""
    now = _now_iso()
    updates: Dict[str, Any] = {
        "last_accessed_at": now,
        "expires_at": _expires_at_iso(now),
    }
    if locked is not None:
        updates["locked"] = locked
    return update_job(job_id, updates)


def start_step(job_id: str, step_name: str) -> None:
    """Mark a step as running, idempotent for repeats."""
    job = load_job(job_id)
    if not job:
        return
    steps = job.get("steps", [])
    if steps and steps[-1].get("name") == step_name and steps[-1].get("status") == "running":
        return
    steps.append(
        {
            "name": step_name,
            "status": "running",
            "started_at": _now_iso(),
            "ended_at": None,
        }
    )
    update_job(job_id, {"steps": steps})


def complete_step(job_id: str, step_name: str) -> None:
    """Mark a step as completed, idempotent for repeats."""
    job = load_job(job_id)
    if not job:
        return
    steps = job.get("steps", [])
    target = None
    for step in reversed(steps):
        if step.get("name") == step_name and step.get("status") in {"running", "pending"}:
            target = step
            break
    if target is None:
        steps.append(
            {
                "name": step_name,
                "status": "completed",
                "started_at": _now_iso(),
                "ended_at": _now_iso(),
            }
        )
    else:
        target["status"] = "completed"
        target["ended_at"] = _now_iso()
    update_job(job_id, {"steps": steps})


def fail_step(job_id: str, step_name: str, error_code: str) -> None:
    """Mark a step as failed, idempotent for repeats."""
    job = load_job(job_id)
    if not job:
        return
    steps = job.get("steps", [])
    target = None
    for step in reversed(steps):
        if step.get("name") == step_name and step.get("status") in {"running", "pending"}:
            target = step
            break
    if target is None:
        steps.append(
            {
                "name": step_name,
                "status": "failed",
                "started_at": _now_iso(),
                "ended_at": _now_iso(),
                "error_code": error_code,
            }
        )
    else:
        target["status"] = "failed"
        target["ended_at"] = _now_iso()
        target["error_code"] = error_code
    update_job(job_id, {"steps": steps})


def fail_running_step(job_id: str, error_code: str) -> None:
    """Fail the most recent running step if present."""
    job = load_job(job_id)
    if not job:
        return
    steps = job.get("steps", [])
    target = None
    for step in reversed(steps):
        if step.get("status") == "running":
            target = step
            break
    if not target:
        return
    target["status"] = "failed"
    target["ended_at"] = _now_iso()
    target["error_code"] = error_code
    update_job(job_id, {"steps": steps})


def last_failed_step(job: Dict[str, Any]) -> Optional[str]:
    """Return the last failed step name for a job."""
    steps = job.get("steps", [])
    for step in reversed(steps):
        if step.get("status") == "failed":
            return step.get("name")
    return None


def update_job_status(job_id: str, status: str, error: Optional[str] = None) -> Optional[Dict[str, Any]]:
    """Set job status and error."""
    updates: Dict[str, Any] = {"status": status, "error": error}
    return update_job(job_id, updates)


def enqueue_job(job_id: str) -> None:
    """Queue a job for background processing."""
    if _redis_enabled():
        queue = _get_rq_queue()
        if queue is None:
            return
        job_payload = load_job(job_id)
        if not job_payload:
            return
        try:
            existing = queue.fetch_job(job_id)
            if existing and existing.get_status() in {"queued", "started", "deferred"}:
                return
        except Exception:
            pass
        try:
            queue.enqueue(
                "app.services.jobs.process_job",
                job_id,
                job_id=job_id,
                retry=None,
                job_timeout=_job_timeout(job_payload),
            )
        except Exception:
            return
        return
    with _queue_lock:
        if job_id in _enqueued:
            return
        _enqueued.add(job_id)
        _queue.put(job_id)


def _iter_jobs() -> Iterable[Dict[str, Any]]:
    for path in JOBS_DIR.glob("*.json"):
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except OSError:
            continue
        except json.JSONDecodeError:
            continue
        yield data


def find_active_job(job_type: str, predicate: Callable[[Dict[str, Any]], bool]) -> Optional[Dict[str, Any]]:
    """Return an existing queued/running job that matches predicate."""
    for job in _iter_jobs():
        if job.get("type") != job_type:
            continue
        if job.get("status") not in {"queued", "running"}:
            continue
        if predicate(job):
            return job
    return None


def _is_locked(job: Dict[str, Any]) -> bool:
    if not job.get("locked"):
        return False
    last_accessed = _parse_iso(job.get("last_accessed_at"))
    if not last_accessed:
        return False
    return _utcnow() - last_accessed <= timedelta(minutes=JOB_LOCK_TTL_MINUTES)


def list_recent_jobs(
    limit: Optional[int] = None,
    owner_session_id: Optional[str] = None,
    owner_user_id: Optional[int] = None,
) -> list[Dict[str, Any]]:
    """Return recent jobs sorted by last access."""
    limit = limit or JOB_RECENT_LIMIT
    now = _utcnow()
    jobs = []
    for job in _iter_jobs():
        expires_at = _parse_iso(job.get("expires_at"))
        if expires_at and expires_at <= now:
            continue
        if owner_user_id is not None:
            if job.get("owner_user_id") != owner_user_id:
                if owner_session_id and job.get("owner_session_id") == owner_session_id and job.get("owner_user_id") is None:
                    pass
                else:
                    continue
        elif owner_session_id and job.get("owner_session_id") != owner_session_id:
            continue
        jobs.append(job)
    jobs.sort(
        key=lambda item: _parse_iso(item.get("last_accessed_at")) or datetime.min.replace(tzinfo=timezone.utc),
        reverse=True,
    )
    return jobs[:limit]


def delete_job(job_id: str) -> bool:
    """Delete a job JSON file and related output artifacts."""
    path = _job_path(job_id)
    if not path.exists():
        return False
    try:
        job = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return False
    if job.get("pinned") and _is_locked(job):
        return False
    try:
        path.unlink()
    except OSError:
        return False
    prefixes = [
        f"{job_id}.",
        f"{job_id}_preview.",
        f"{job_id}_karaoke.",
        f"{job_id}_transcript_words.",
    ]
    for file_path in OUTPUTS_DIR.glob(f"{job_id}*"):
        name = file_path.name
        if any(name.startswith(prefix) for prefix in prefixes):
            try:
                file_path.unlink()
            except OSError:
                continue
    return True


def retry_job(job_id: str) -> Optional[Dict[str, Any]]:
    """Re-queue a failed job with the same inputs."""
    job = load_job(job_id)
    if not job:
        return None
    if job.get("status") != "failed":
        return job
    updates = {
        "status": "queued",
        "error": None,
        "steps": [],
        "log_path": None,
    }
    updated = update_job(job_id, updates)
    if updated:
        enqueue_job(job_id)
    return updated


def cleanup_jobs() -> None:
    """Remove old job files to limit disk usage."""
    if JOB_MAX_AGE_HOURS <= 0:
        return
    cutoff = _utcnow() - timedelta(hours=JOB_MAX_AGE_HOURS)
    deleted = 0
    for path in JOBS_DIR.glob("*.json"):
        try:
            modified = datetime.fromtimestamp(path.stat().st_mtime, tz=timezone.utc)
        except OSError:
            continue
        if modified >= cutoff:
            continue
        try:
            job = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        if job.get("status") not in {"completed", "failed"}:
            continue
        if job.get("pinned"):
            last_accessed = _parse_iso(job.get("last_accessed_at"))
            if last_accessed:
                pinned_cutoff = _utcnow() - timedelta(days=JOB_PINNED_RETENTION_DAYS)
                if last_accessed > pinned_cutoff:
                    continue
            else:
                continue
        if _is_locked(job):
            continue
        expires_at = _parse_iso(job.get("expires_at"))
        if expires_at and expires_at > _utcnow():
            continue
        try:
            path.unlink()
            deleted += 1
            if deleted >= JOB_CLEANUP_BATCH:
                break
        except OSError:
            continue


def _rehydrate_queue() -> None:
    for job in _iter_jobs():
        status = job.get("status")
        job_id = job.get("job_id")
        if not job_id:
            continue
        if status == "running":
            update_job_status(job_id, "queued")
            enqueue_job(job_id)
        elif status == "queued":
            enqueue_job(job_id)


def process_job(job_id: str) -> None:
    """Process a job by ID (used by local worker and RQ)."""
    from app.services.tasks import run_job  # local import to avoid cycles

    job = load_job(job_id)
    if not job:
        return
    log_path = JOB_LOG_DIR / f"{job_id}.log"
    job["log_path"] = str(log_path)
    update_job(job_id, {"log_path": str(log_path)})
    update_job_status(job_id, "running")
    try:
        output = run_job(job)
    except Exception as exc:  # noqa: BLE001 - explicit error capture
        payload = getattr(exc, "error_payload", None)
        if not isinstance(payload, dict):
            payload = {
                "code": "UNKNOWN",
                "message": "Something went wrong while processing this job.",
                "hint": "Try again or contact support if this keeps happening.",
            }
        fail_running_step(job_id, payload.get("code", "UNKNOWN"))
        update_job(job_id, {"status": "failed", "error": payload})
        try:
            log_path.write_text(str(exc), encoding="utf-8")
        except OSError:
            pass
    else:
        update_job(job_id, {"status": "completed", "output": output, "error": None})


def _worker_loop() -> None:
    while True:
        job_id = _queue.get()
        with _queue_lock:
            _enqueued.discard(job_id)
        try:
            process_job(job_id)
        finally:
            _queue.task_done()


def start_workers() -> None:
    """Start background worker threads if not already running."""
    global _workers_started
    if _workers_started:
        return
    cleanup_jobs()
    _rehydrate_queue()
    if _redis_enabled():
        _workers_started = True
        return
    for _ in range(max(1, JOB_WORKER_COUNT)):
        thread = threading.Thread(target=_worker_loop, daemon=True)
        thread.start()
    _workers_started = True
