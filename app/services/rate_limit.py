"""Simple in-memory rate limiter (per-process)."""

from __future__ import annotations

import time
from typing import Tuple

_buckets: dict[str, tuple[int, float]] = {}


def check_rate_limit(key: str, limit: int, window_seconds: int) -> Tuple[bool, int]:
    """Return (allowed, retry_after_seconds)."""
    now = time.time()
    count, reset_at = _buckets.get(key, (0, now + window_seconds))
    if now >= reset_at:
        count = 0
        reset_at = now + window_seconds
    if count >= limit:
        retry_after = max(1, int(reset_at - now))
        return False, retry_after
    _buckets[key] = (count + 1, reset_at)
    return True, 0
