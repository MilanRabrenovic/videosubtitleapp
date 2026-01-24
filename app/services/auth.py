"""Minimal auth with SQLite-backed users and sessions."""

from __future__ import annotations

import hashlib
import hmac
import os
import secrets
import sqlite3
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Optional

from app.config import AUTH_COOKIE_NAME, AUTH_DB_PATH, AUTH_SESSION_DAYS


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _now_iso() -> str:
    return _utcnow().isoformat(timespec="seconds").replace("+00:00", "Z")


def _parse_iso(value: str) -> datetime:
    return datetime.fromisoformat(value.replace("Z", "+00:00")).astimezone(timezone.utc)


def _connect() -> sqlite3.Connection:
    conn = sqlite3.connect(str(AUTH_DB_PATH))
    conn.row_factory = sqlite3.Row
    return conn


def init_auth_db() -> None:
    """Initialize auth database tables."""
    with _connect() as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                email TEXT UNIQUE NOT NULL,
                password_hash TEXT NOT NULL,
                created_at TEXT NOT NULL
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS sessions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                token TEXT UNIQUE NOT NULL,
                created_at TEXT NOT NULL,
                expires_at TEXT NOT NULL,
                FOREIGN KEY(user_id) REFERENCES users(id)
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS presets (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                name TEXT NOT NULL,
                style_json TEXT NOT NULL,
                created_at TEXT NOT NULL,
                UNIQUE(user_id, name),
                FOREIGN KEY(user_id) REFERENCES users(id)
            )
            """
        )


def _hash_password(password: str) -> str:
    salt = os.urandom(16)
    iterations = 200_000
    digest = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, iterations)
    return f"pbkdf2_sha256${iterations}${salt.hex()}${digest.hex()}"


def _verify_password(password: str, stored: str) -> bool:
    try:
        scheme, iterations, salt_hex, digest_hex = stored.split("$", 3)
        if scheme != "pbkdf2_sha256":
            return False
        digest = hashlib.pbkdf2_hmac(
            "sha256",
            password.encode("utf-8"),
            bytes.fromhex(salt_hex),
            int(iterations),
        )
        return hmac.compare_digest(digest.hex(), digest_hex)
    except Exception:
        return False


def create_user(email: str, password: str) -> Optional[int]:
    """Create a new user. Returns user id or None if exists."""
    email = email.strip().lower()
    if not email or not password:
        return None
    password_hash = _hash_password(password)
    try:
        with _connect() as conn:
            cursor = conn.execute(
                "INSERT INTO users (email, password_hash, created_at) VALUES (?, ?, ?)",
                (email, password_hash, _now_iso()),
            )
            return int(cursor.lastrowid)
    except sqlite3.IntegrityError:
        return None


def authenticate_user(email: str, password: str) -> Optional[int]:
    """Return user id if credentials are valid."""
    email = email.strip().lower()
    with _connect() as conn:
        row = conn.execute("SELECT id, password_hash FROM users WHERE email = ?", (email,)).fetchone()
    if not row:
        return None
    if not _verify_password(password, row["password_hash"]):
        return None
    return int(row["id"])


def create_session(user_id: int) -> str:
    """Create a session token for user."""
    token = secrets.token_urlsafe(32)
    created_at = _now_iso()
    expires_at = (_utcnow() + timedelta(days=AUTH_SESSION_DAYS)).isoformat(timespec="seconds").replace("+00:00", "Z")
    with _connect() as conn:
        conn.execute(
            "INSERT INTO sessions (user_id, token, created_at, expires_at) VALUES (?, ?, ?, ?)",
            (user_id, token, created_at, expires_at),
        )
    return token


def get_user_by_session(token: str) -> Optional[dict]:
    """Return user row if session token is valid."""
    if not token:
        return None
    with _connect() as conn:
        session = conn.execute(
            "SELECT user_id, expires_at FROM sessions WHERE token = ?",
            (token,),
        ).fetchone()
        if not session:
            return None
        expires_at = _parse_iso(session["expires_at"])
        if expires_at <= _utcnow():
            conn.execute("DELETE FROM sessions WHERE token = ?", (token,))
            return None
        user = conn.execute(
            "SELECT id, email FROM users WHERE id = ?",
            (session["user_id"],),
        ).fetchone()
        if not user:
            return None
    return {"id": int(user["id"]), "email": user["email"]}


def destroy_session(token: str) -> None:
    if not token:
        return
    with _connect() as conn:
        conn.execute("DELETE FROM sessions WHERE token = ?", (token,))


@dataclass
class AuthContext:
    user: Optional[dict]
    token: Optional[str]


def get_auth_context(request) -> AuthContext:
    token = request.cookies.get(AUTH_COOKIE_NAME)
    user = get_user_by_session(token) if token else None
    return AuthContext(user=user, token=token)
