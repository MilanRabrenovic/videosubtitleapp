"""Storage cleanup helpers for uploads/outputs."""

from __future__ import annotations

import re
from pathlib import Path
from typing import Dict, List

from app.config import OUTPUTS_DIR, UPLOADS_DIR

JOB_ID_PATTERN = re.compile(r"^([0-9a-f]{32})")


def _job_id_for_file(path: Path) -> str | None:
    match = JOB_ID_PATTERN.match(path.name)
    if not match:
        return None
    return match.group(1)


def _collect_job_files() -> Dict[str, List[Path]]:
    jobs: Dict[str, List[Path]] = {}
    for root in (UPLOADS_DIR, OUTPUTS_DIR):
        for item in root.iterdir():
            if item.is_dir():
                if item.name == "fonts":
                    continue
                continue
            job_id = _job_id_for_file(item)
            if not job_id:
                continue
            jobs.setdefault(job_id, []).append(item)
    return jobs


def _job_stats(paths: List[Path]) -> tuple[int, float]:
    total_size = 0
    latest_mtime = 0.0
    for path in paths:
        try:
            stat = path.stat()
        except OSError:
            continue
        total_size += stat.st_size
        latest_mtime = max(latest_mtime, stat.st_mtime)
    return total_size, latest_mtime


def cleanup_storage(max_bytes: int) -> None:
    """Delete oldest jobs until total storage is under max_bytes."""
    jobs = _collect_job_files()
    totals: Dict[str, int] = {}
    latest: Dict[str, float] = {}
    total_size = 0
    for job_id, paths in jobs.items():
        size, mtime = _job_stats(paths)
        totals[job_id] = size
        latest[job_id] = mtime
        total_size += size

    if total_size <= max_bytes:
        return

    for job_id in sorted(latest, key=lambda key: latest[key]):
        for path in jobs.get(job_id, []):
            try:
                path.unlink()
            except OSError:
                continue
        total_size -= totals.get(job_id, 0)
        if total_size <= max_bytes:
            break


def touch_job(job_id: str) -> None:
    """Update mtime for all files belonging to a job."""
    if not job_id:
        return
    for root in (UPLOADS_DIR, OUTPUTS_DIR):
        for item in root.iterdir():
            if item.is_dir():
                if item.name == "fonts":
                    continue
                continue
            if not item.name.startswith(job_id):
                continue
            try:
                item.touch()
            except OSError:
                continue
