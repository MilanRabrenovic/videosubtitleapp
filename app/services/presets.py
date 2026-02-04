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
            "id": "builtin:white-on-black",
            "name": "White on Black",
            "style": {
                "font_family": "Arial",
                "font_weight": 400,
                "font_style": "regular",
                "font_size": 42,
                "text_color": "#FFFFFF",
                "highlight_color": "#FFFFFF",
                "highlight_mode": "text",
                "highlight_opacity": 1.0,
                "highlight_text_opacity": 1.0,
                "outline_color": "#000000",
                "outline_enabled": False,
                "outline_size": 0,
                "background_enabled": True,
                "background_color": "#000000",
                "background_opacity": 0.8,
                "background_padding": 12,
                "background_blur": 0.0,
                "line_height": 6,
                "position": "bottom",
                "margin_v": 50,
                "max_words_per_line": 8,
            },
        },
        {
            "id": "builtin:capcut-word",
            "name": "CapCut Word-by-Word",
            "style": {
                "font_family": "Montserrat",
                "font_weight": 700,
                "font_style": "regular",
                "font_size": 48,
                "text_color": "#FFFFFF",
                "highlight_color": "#FFD700",
                "highlight_mode": "text",
                "highlight_opacity": 1.0,
                "highlight_text_opacity": 1.0,
                "outline_enabled": True,
                "outline_color": "#000000",
                "outline_size": 4,
                "background_enabled": False,
                "background_color": "#000000",
                "background_opacity": 0.6,
                "background_padding": 8,
                "background_blur": 0.0,
                "line_height": 6,
                "position": "bottom",
                "margin_v": 55,
                "max_words_per_line": 7,
            },
        },
        {
            "id": "builtin:capcut-box",
            "name": "CapCut Highlight Box",
            "style": {
                "font_family": "Montserrat",
                "font_weight": 700,
                "font_style": "regular",
                "font_size": 46,
                "text_color": "#FFFFFF",
                "highlight_color": "#FFD700",
                "highlight_mode": "background",
                "highlight_opacity": 0.85,
                "highlight_text_opacity": 1.0,
                "outline_enabled": False,
                "outline_color": "#000000",
                "outline_size": 2,
                "background_enabled": True,
                "background_color": "#0A0A0A",
                "background_opacity": 0.55,
                "background_padding": 10,
                "background_blur": 0.0,
                "line_height": 6,
                "position": "bottom",
                "margin_v": 50,
                "max_words_per_line": 7,
            },
        },
        {
            "id": "builtin:classic-outline",
            "name": "Classic Broadcast",
            "style": {
                "font_family": "Arial",
                "font_weight": 600,
                "font_style": "regular",
                "font_size": 44,
                "text_color": "#FFFFFF",
                "highlight_color": "#FFFFFF",
                "highlight_mode": "text",
                "highlight_opacity": 1.0,
                "highlight_text_opacity": 1.0,
                "outline_enabled": True,
                "outline_color": "#000000",
                "outline_size": 4,
                "background_enabled": False,
                "background_color": "#000000",
                "background_opacity": 0.4,
                "background_padding": 8,
                "background_blur": 0.0,
                "line_height": 6,
                "position": "bottom",
                "margin_v": 60,
                "max_words_per_line": 8,
            },
        },
        {
            "id": "builtin:word-fill",
            "name": "Word Fill (cumulative)",
            "style": {
                "font_family": "Montserrat",
                "font_weight": 600,
                "font_style": "regular",
                "font_size": 44,
                "text_color": "#FFFFFF",
                "highlight_color": "#00E5FF",
                "highlight_mode": "text_cumulative",
                "highlight_opacity": 1.0,
                "highlight_text_opacity": 1.0,
                "outline_enabled": True,
                "outline_color": "#0F172A",
                "outline_size": 3,
                "background_enabled": False,
                "background_color": "#000000",
                "background_opacity": 0.4,
                "background_padding": 6,
                "background_blur": 0.0,
                "line_height": 5,
                "position": "bottom",
                "margin_v": 50,
                "max_words_per_line": 8,
            },
        },
    ]
