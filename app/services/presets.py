"""Subtitle styling presets (built-in + user-saved)."""

from __future__ import annotations

import json
import sqlite3
from typing import Any, Dict, List

from app.config import AUTH_DB_PATH


def _connect() -> sqlite3.Connection:
    conn = sqlite3.connect(str(AUTH_DB_PATH))
    conn.row_factory = sqlite3.Row
    return conn


def list_user_presets(user_id: int) -> List[Dict[str, Any]]:
    with _connect() as conn:
        rows = conn.execute(
            "SELECT id, name, style_json FROM presets WHERE user_id = ? ORDER BY id ASC",
            (user_id,),
        ).fetchall()
    presets: List[Dict[str, Any]] = []
    for row in rows:
        try:
            style = json.loads(row["style_json"])
        except json.JSONDecodeError:
            style = {}
        presets.append({"id": str(row["id"]), "name": row["name"], "style": style})
    return presets


def save_user_preset(user_id: int, name: str, style: Dict[str, Any]) -> Dict[str, Any] | None:
    name = name.strip()
    if not name:
        return None
    payload = json.dumps(style)
    with _connect() as conn:
        try:
            cursor = conn.execute(
                "INSERT INTO presets (user_id, name, style_json, created_at) VALUES (?, ?, ?, datetime('now'))",
                (user_id, name, payload),
            )
            preset_id = int(cursor.lastrowid)
        except sqlite3.IntegrityError:
            return None
    return {"id": str(preset_id), "name": name, "style": style}


def builtin_presets() -> List[Dict[str, Any]]:
    return [
        {
            "id": "builtin:tiktok-classic",
            "name": "Social Classic",
            "style": {
                "font_family": "Montserrat",
                "font_weight": 700,
                "font_style": "regular",
                "font_size": 48,
                "text_color": "#FFFFFF",
                "highlight_color": "#FFFF00",
                "outline_color": "#000000",
                "outline_enabled": True,
                "outline_size": 4,
                "background_enabled": False,
                "background_color": "#000000",
                "background_opacity": 0.6,
                "background_padding": 8,
                "background_blur": 0.0,
                "line_height": 6,
                "position": "bottom",
                "margin_v": 50,
                "max_words_per_line": 7,
            },
        },
        {
            "id": "builtin:tiktok-box",
            "name": "Social Box",
            "style": {
                "font_family": "Montserrat",
                "font_weight": 700,
                "font_style": "regular",
                "font_size": 46,
                "text_color": "#FFFFFF",
                "highlight_color": "#FFFF00",
                "outline_enabled": False,
                "outline_color": "#000000",
                "outline_size": 2,
                "background_enabled": True,
                "background_color": "#000000",
                "background_opacity": 0.55,
                "background_padding": 10,
                "background_blur": 0.0,
                "line_height": 6,
                "position": "bottom",
                "margin_v": 60,
                "max_words_per_line": 7,
            },
        },
        {
            "id": "builtin:clean-bold",
            "name": "Clean Bold",
            "style": {
                "font_family": "Montserrat",
                "font_weight": 700,
                "font_style": "regular",
                "font_size": 48,
                "text_color": "#FFFFFF",
                "highlight_color": "#FFD400",
                "outline_enabled": True,
                "outline_color": "#111111",
                "outline_size": 3,
                "background_enabled": False,
                "background_color": "#000000",
                "background_opacity": 0.5,
                "background_padding": 8,
                "background_blur": 0.0,
                "line_height": 6,
                "position": "bottom",
                "margin_v": 50,
                "max_words_per_line": 7,
            },
        },
        {
            "id": "builtin:modern-soft",
            "name": "Modern Soft",
            "style": {
                "font_family": "Manrope",
                "font_weight": 600,
                "font_style": "regular",
                "font_size": 46,
                "text_color": "#FFFFFF",
                "highlight_color": "#A7F3D0",
                "outline_enabled": False,
                "outline_color": "#000000",
                "outline_size": 2,
                "background_enabled": True,
                "background_color": "#0F172A",
                "background_opacity": 0.45,
                "background_padding": 10,
                "background_blur": 0.0,
                "line_height": 6,
                "position": "bottom",
                "margin_v": 60,
                "max_words_per_line": 8,
            },
        },
        {
            "id": "builtin:headline",
            "name": "Headline Pop",
            "style": {
                "font_family": "Bebas Neue",
                "font_weight": 700,
                "font_style": "regular",
                "font_size": 56,
                "text_color": "#FFFFFF",
                "highlight_color": "#F97316",
                "outline_enabled": True,
                "outline_color": "#000000",
                "outline_size": 4,
                "background_enabled": False,
                "background_color": "#000000",
                "background_opacity": 0.6,
                "background_padding": 8,
                "background_blur": 0.0,
                "line_height": 7,
                "position": "bottom",
                "margin_v": 55,
                "max_words_per_line": 7,
            },
        },
    ]
