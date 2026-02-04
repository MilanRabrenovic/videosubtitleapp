"""Health check endpoints."""

from pathlib import Path
from typing import Any, Dict

from fastapi import APIRouter

from app.config import AUTH_DB_PATH, JOBS_DIR, OUTPUTS_DIR, UPLOADS_DIR, REDIS_URL

router = APIRouter()


@router.get("/health")
def health() -> Dict[str, str]:
    return {"status": "ok"}


@router.get("/ready")
def ready() -> Dict[str, Any]:
    checks: Dict[str, Any] = {"status": "ok"}
    checks["uploads_dir"] = UPLOADS_DIR.exists()
    checks["outputs_dir"] = OUTPUTS_DIR.exists()
    checks["jobs_dir"] = JOBS_DIR.exists()
    checks["auth_db"] = AUTH_DB_PATH.exists()
    if REDIS_URL:
        try:
            import redis

            conn = redis.from_url(REDIS_URL)
            conn.ping()
            checks["redis"] = True
        except Exception:
            checks["redis"] = False
            checks["status"] = "degraded"
    return checks
