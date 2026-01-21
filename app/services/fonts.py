"""Helpers for Google Fonts selection and downloads."""

from __future__ import annotations

import hashlib
import io
import re
import urllib.parse
import urllib.request
import zipfile
from pathlib import Path
from typing import Iterable, Optional

from app.config import FONTS_DIR

try:
    from fontTools.ttLib import TTFont
except ImportError:  # pragma: no cover - optional dependency
    TTFont = None

GOOGLE_FONTS: list[str] = [
    "Roboto",
    "Open Sans",
    "Montserrat",
    "Poppins",
    "Raleway",
    "Merriweather",
    "Playfair Display",
    "Oswald",
    "Bebas Neue",
    "Manrope",
]

SYSTEM_FONTS: list[str] = [
    "Arial",
    "Verdana",
    "Helvetica",
]


def normalize_font_name(font_name: Optional[str]) -> Optional[str]:
    """Return the canonical Google Font name if it matches case-insensitively."""
    if not font_name:
        return None
    candidate = font_name.strip().lower()
    for font in GOOGLE_FONTS:
        if font.lower() == candidate:
            return font
    return None


def is_google_font(font_name: Optional[str]) -> bool:
    """Return True if the font is in the supported Google Fonts list."""
    return normalize_font_name(font_name) is not None


def google_fonts_css_url(font_name: str) -> str:
    """Return the Google Fonts CSS URL for preview usage."""
    family = urllib.parse.quote_plus(font_name.strip())
    return f"https://fonts.googleapis.com/css2?family={family}:wght@400;700&display=swap"


def _font_dir(font_name: str) -> Path:
    safe = re.sub(r"[^A-Za-z0-9_-]+", "-", font_name.strip())
    return FONTS_DIR / safe


def _job_fonts_dir(job_id: str) -> Path:
    return FONTS_DIR / "jobs" / job_id


def _google_fonts_dir(font_name: str) -> Path:
    safe = re.sub(r"[^A-Za-z0-9_-]+", "-", font_name.strip())
    return FONTS_DIR / "google" / safe


def font_dir_for_name(font_name: Optional[str], job_id: Optional[str] = None) -> Optional[Path]:
    """Return the font directory for a name if it exists and has font files."""
    if job_id:
        job_dir = _job_fonts_dir(job_id)
        if any(job_dir.glob("*.ttf")) or any(job_dir.glob("*.otf")):
            return job_dir
    if not font_name:
        return None
    google_dir = _google_fonts_dir(font_name)
    if any(google_dir.glob("*.ttf")) or any(google_dir.glob("*.otf")):
        return google_dir
    target_dir = _font_dir(font_name)
    if any(target_dir.glob("*.ttf")) or any(target_dir.glob("*.otf")):
        return target_dir
    return None


def delete_font_family(font_name: Optional[str], job_id: Optional[str]) -> bool:
    """Delete uploaded font files for a job."""
    if not font_name or not job_id:
        return False
    job_dir = _job_fonts_dir(job_id)
    if not job_dir.exists():
        return False
    deleted = False
    for item in job_dir.iterdir():
        if not item.is_file():
            continue
        try:
            with item.open("rb") as handle:
                data = handle.read()
            family, full_name, _, _ = detect_font_info(data, item.name)
            if family == font_name or full_name == font_name:
                item.unlink()
                deleted = True
        except OSError:
            continue
    try:
        if not any(job_dir.iterdir()):
            job_dir.rmdir()
    except OSError:
        pass
    return deleted


def _system_font_dirs() -> list[Path]:
    return [
        Path("/Library/Fonts"),
        Path("/System/Library/Fonts"),
        Path.home() / "Library" / "Fonts",
    ]


def find_system_font_dir(font_name: str) -> Optional[Path]:
    """Find a system-installed font directory by name."""
    needle = font_name.strip().lower()
    for font_dir in _system_font_dirs():
        if not font_dir.exists():
            continue
        for font_file in font_dir.rglob("*.ttf"):
            if needle in font_file.stem.lower():
                return font_file.parent
        for font_file in font_dir.rglob("*.otf"):
            if needle in font_file.stem.lower():
                return font_file.parent
    return None


def ensure_font_downloaded(font_name: Optional[str]) -> Optional[Path]:
    """Download the Google Font family zip if needed; return the font directory."""
    canonical = normalize_font_name(font_name)
    if not canonical:
        return None
    target_dir = _google_fonts_dir(canonical)
    target_dir.mkdir(parents=True, exist_ok=True)
    if any(target_dir.glob("*.ttf")) or any(target_dir.glob("*.otf")):
        return target_dir

    family = urllib.parse.quote_plus(canonical.strip())
    url = f"https://fonts.google.com/download?family={family}"
    zip_path = target_dir / "family.zip"
    try:
        request = urllib.request.Request(
            url,
            headers={"User-Agent": "Mozilla/5.0"},
        )
        with urllib.request.urlopen(request, timeout=30) as response:
            zip_path.write_bytes(response.read())
    except Exception:
        return find_system_font_dir(canonical)

    try:
        with zipfile.ZipFile(zip_path) as archive:
            for member in archive.namelist():
                if member.lower().endswith((".ttf", ".otf")):
                    archive.extract(member, target_dir)
    except zipfile.BadZipFile:
        return find_system_font_dir(canonical)
    finally:
        zip_path.unlink(missing_ok=True)

    for nested in target_dir.rglob("*.ttf"):
        if nested.parent != target_dir:
            nested.replace(target_dir / nested.name)
    for nested in target_dir.rglob("*.otf"):
        if nested.parent != target_dir:
            nested.replace(target_dir / nested.name)
    if any(target_dir.glob("*.ttf")) or any(target_dir.glob("*.otf")):
        return target_dir
    return find_system_font_dir(canonical)


def available_fonts() -> Iterable[str]:
    """Return the list of supported Google Fonts plus system fonts."""
    return list(SYSTEM_FONTS) + list(GOOGLE_FONTS)


def google_font_choices() -> list[str]:
    """Return the curated Google Fonts list."""
    return list(GOOGLE_FONTS)


def system_font_choices() -> list[str]:
    """Return the system font list."""
    return list(SYSTEM_FONTS)


def available_local_fonts(job_id: Optional[str]) -> list[str]:
    """Return font family names from uploaded font files for a job."""
    fonts: list[str] = []
    if not job_id:
        return fonts
    job_dir = _job_fonts_dir(job_id)
    if not job_dir.exists():
        return fonts
    for path in job_dir.iterdir():
        if not path.is_file():
            continue
        if path.suffix.lower() not in {".ttf", ".otf"}:
            continue
        try:
            data = path.read_bytes()
        except OSError:
            continue
        family, full_name, _, _ = detect_font_info(data, path.name)
        if family:
            fonts.append(family)
        elif full_name:
            fonts.append(full_name)
    return sorted(set(fonts))


def available_local_font_variants(job_id: Optional[str]) -> list[dict]:
    """Return font variant metadata for a job."""
    variants: list[dict] = []
    if not job_id:
        return variants
    job_dir = _job_fonts_dir(job_id)
    if not job_dir.exists():
        return variants
    for path in job_dir.iterdir():
        if not path.is_file() or path.suffix.lower() not in {".ttf", ".otf"}:
            continue
        try:
            data = path.read_bytes()
        except OSError:
            continue
        family, full_name, italic, weight = detect_font_info(data, path.name)
        if not family and not full_name:
            continue
        variants.append(
            {
                "family": family or full_name,
                "full_name": full_name or family,
                "italic": italic,
                "weight": int(weight) if weight else 400,
                "path": str(path),
            }
        )
    return variants


def available_google_font_variants(font_name: Optional[str]) -> list[dict]:
    """Return font variant metadata from cached Google fonts."""
    if not font_name:
        return []
    google_dir = _google_fonts_dir(font_name)
    if not google_dir.exists():
        return []
    variants: list[dict] = []
    for path in google_dir.iterdir():
        if not path.is_file() or path.suffix.lower() not in {".ttf", ".otf"}:
            continue
        try:
            data = path.read_bytes()
        except OSError:
            continue
        family, full_name, italic, weight = detect_font_info(data, path.name)
        if not family and not full_name:
            continue
        variants.append(
            {
                "family": family or full_name,
                "full_name": full_name or family,
                "italic": italic,
                "weight": int(weight) if weight else 400,
                "path": str(path),
            }
        )
    return variants


def font_files_available(font_name: Optional[str]) -> bool:
    """Return True if font files exist locally for the given font."""
    canonical = normalize_font_name(font_name)
    if not canonical:
        return font_dir_for_name(font_name) is not None
    google_dir = _google_fonts_dir(canonical)
    if any(google_dir.glob("*.ttf")) or any(google_dir.glob("*.otf")):
        return True
    target_dir = _font_dir(canonical)
    if any(target_dir.glob("*.ttf")) or any(target_dir.glob("*.otf")):
        return True
    return find_system_font_dir(canonical) is not None


def guess_font_family(filename: Optional[str]) -> Optional[str]:
    """Guess a font family name from a font filename."""
    if not filename:
        return None
    name = Path(filename).stem
    name = re.sub(r"([a-z])([A-Z])", r"\1 \2", name)
    name = re.sub(r"[_-]+", " ", name)
    name = re.sub(r"(?i)\\b(regular|bold|italic|light|medium|thin|black|semibold|extrabold|extralight)\\b", "", name)
    name = re.sub(r"\\s+", " ", name).strip()
    return name or None


def _decode_name(record) -> Optional[str]:
    try:
        return record.toUnicode().strip()
    except Exception:
        try:
            return record.string.decode("utf-8", errors="ignore").strip()
        except Exception:
            return None


def detect_font_info(data: bytes, filename: Optional[str]) -> tuple[Optional[str], Optional[str], bool, int]:
    """Detect font family/full name, italic flag, and weight from font data."""
    if TTFont is None:
        family = guess_font_family(filename)
        return family, family, False, 400
    try:
        font = TTFont(io.BytesIO(data))
        names = font["name"].names
        family = None
        full_name = None
        style_name = None
        weight_value = 400
        for record in names:
            if record.nameID == 16 and family is None:
                family = _decode_name(record)
            elif record.nameID == 1 and family is None:
                family = _decode_name(record)
            elif record.nameID == 4 and full_name is None:
                full_name = _decode_name(record)
            elif record.nameID == 17 and style_name is None:
                style_name = _decode_name(record)
            elif record.nameID == 2 and style_name is None:
                style_name = _decode_name(record)
        try:
            weight_value = int(font["OS/2"].usWeightClass)
        except Exception:
            weight_value = 400
        if not family:
            family = guess_font_family(filename)
        if not full_name:
            full_name = family
        italic = bool(style_name and "italic" in style_name.lower())
        return family, full_name, italic, weight_value
    except Exception:
        family = guess_font_family(filename)
        return family, family, False, 400


def save_uploaded_font(
    font_name: Optional[str], filename: str, data: bytes, job_id: str
) -> Optional[tuple[Path, str, str, bool, int]]:
    """Save an uploaded font file into a local font directory."""
    family, full_name, italic, weight = detect_font_info(data, filename)
    detected_family = family or font_name or ""
    detected_full = full_name or detected_family
    if not detected_family or not filename:
        return None
    ext = Path(filename).suffix.lower()
    if ext not in {".ttf", ".otf"}:
        return None
    target_dir = _job_fonts_dir(job_id)
    target_dir.mkdir(parents=True, exist_ok=True)
    digest = hashlib.sha256(data).hexdigest()[:12]
    target_path = target_dir / f"{Path(filename).stem}-{digest}{Path(filename).suffix}"
    if target_path.exists():
        return target_dir, detected_family, detected_full, italic, weight
    target_path.write_bytes(data)
    return target_dir, detected_family, detected_full, italic, weight
