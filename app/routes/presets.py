"""Preset endpoints."""

from __future__ import annotations

from typing import Any, Dict

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import JSONResponse

from app.services.presets import save_user_preset

router = APIRouter()


def _require_user(request: Request):
    user = getattr(request.state, "user", None)
    if not user:
        raise HTTPException(status_code=401, detail="Authentication required")
    return user


@router.post("/presets")
async def create_preset(request: Request) -> Dict[str, Any]:
    user = _require_user(request)
    payload = await request.json()
    name = (payload.get("name") or "").strip()
    style = payload.get("style") or {}
    if not name:
        raise HTTPException(status_code=400, detail="Preset name is required")
    if len(name) > 40:
        raise HTTPException(status_code=400, detail="Preset name is too long")
    created = save_user_preset(user["id"], name, style)
    if not created:
        raise HTTPException(status_code=400, detail="Unable to save preset (name may already exist)")
    return JSONResponse({"preset": created})
