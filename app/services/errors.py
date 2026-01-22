"""Shared error helpers for background jobs."""

from __future__ import annotations

from typing import Optional


def error_payload(code: str, message: str, hint: Optional[str] = None) -> dict:
    """Return a user-safe error payload."""
    payload = {"code": code, "message": message}
    if hint:
        payload["hint"] = hint
    return payload


class JobError(Exception):
    """Exception carrying a user-facing error payload."""

    def __init__(self, payload: dict, log_message: Optional[str] = None) -> None:
        super().__init__(log_message or payload.get("message", "Job failed"))
        self.error_payload = payload
