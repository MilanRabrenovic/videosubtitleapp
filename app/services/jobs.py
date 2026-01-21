"""File-backed job queue for background processing."""

from __future__ import annotations

import json
import os
import threading
import uuid
from datetime import datetime, timedelta
from pathlib import Path
from queue import Queue
from typing import Any, Callable, Dict, Iterable, Optional

from app.config import JOBS_DIR, JOB_MAX_AGE_HOURS, JOB_WORKER_COUNT

_queue: Queue[str] = Queue()
_queue_lock = threading.Lock()
_write_lock = threading.Lock()
_enqueued: set[str] = set()
_workers_started = False


def _now_iso() -> str:
    return datetime.utcnow().isoformat(timespec="seconds") + "Z"


def _job_path(job_id: str) -> Path:
    return JOBS_DIR / f"{job_id}.json"


def _atomic_write(path: Path, payload: Dict[str, Any]) -> None:
    tmp_path = path.with_suffix(".tmp")
    with _write_lock:
        tmp_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
        os.replace(tmp_path, path)


def create_job(job_type: str, input_data: Dict[str, Any], job_id: Optional[str] = None) -> Dict[str, Any]:
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
    return json.loads(path.read_text(encoding="utf-8"))


def update_job(job_id: str, updates: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """Update job fields and persist."""
    job = load_job(job_id)
    if not job:
        return None
    job.update(updates)
    job["updated_at"] = _now_iso()
    _atomic_write(_job_path(job_id), job)
    return job


def update_job_status(job_id: str, status: str, error: Optional[str] = None) -> Optional[Dict[str, Any]]:
    """Set job status and error."""
    updates: Dict[str, Any] = {"status": status, "error": error}
    return update_job(job_id, updates)


def enqueue_job(job_id: str) -> None:
    """Queue a job for background processing."""
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


def cleanup_jobs() -> None:
    """Remove old job files to limit disk usage."""
    if JOB_MAX_AGE_HOURS <= 0:
        return
    cutoff = datetime.utcnow() - timedelta(hours=JOB_MAX_AGE_HOURS)
    for path in JOBS_DIR.glob("*.json"):
        try:
            modified = datetime.utcfromtimestamp(path.stat().st_mtime)
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
        try:
            path.unlink()
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


def _worker_loop() -> None:
    from app.services.tasks import run_job  # local import to avoid cycles

    while True:
        job_id = _queue.get()
        with _queue_lock:
            _enqueued.discard(job_id)
        job = load_job(job_id)
        if not job:
            _queue.task_done()
            continue
        update_job_status(job_id, "running")
        try:
            output = run_job(job)
        except Exception as exc:  # noqa: BLE001 - explicit error capture
            update_job_status(job_id, "failed", str(exc))
        else:
            update_job(job_id, {"status": "completed", "output": output, "error": None})
        finally:
            _queue.task_done()


def start_workers() -> None:
    """Start background worker threads if not already running."""
    global _workers_started
    if _workers_started:
        return
    cleanup_jobs()
    _rehydrate_queue()
    for _ in range(max(1, JOB_WORKER_COUNT)):
        thread = threading.Thread(target=_worker_loop, daemon=True)
        thread.start()
    _workers_started = True
