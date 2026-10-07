"""Detect what an uploaded file really is from its content (magic bytes), not its name."""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

import filetype

from app.core.enums import MediaKind
from app.services.search_text import transliterate_uk

IMAGE_TYPES = {
    "image/jpeg",
    "image/png",
    "image/gif",
    "image/webp",
    "image/tiff",
    "image/bmp",
    "image/heic",
    "image/heif",
    "image/avif",
}
AUDIO_TYPES = {
    "audio/mpeg",
    "audio/mp4",
    "audio/m4a",
    "audio/x-m4a",
    "audio/aac",
    "audio/x-aac",
    "audio/ogg",
    "audio/x-wav",
    "audio/wav",
    "audio/x-flac",
    "audio/flac",
    "audio/amr",
    "audio/webm",
}
VIDEO_TYPES = {
    "video/mp4",
    "video/quicktime",
    "video/webm",
    "video/x-matroska",
    "video/x-msvideo",
    "video/mpeg",
    "video/3gpp",
    "video/x-m4v",
}
DOCUMENT_TYPES = {
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    "application/vnd.oasis.opendocument.text",
    "application/msword",
    "application/rtf",
}
TEXT_EXTENSIONS = {".txt", ".md", ".csv"}

# Formats every browser can play directly (no web version needed).
BROWSER_AUDIO = {
    "audio/mpeg",
    "audio/mp4",
    "audio/m4a",
    "audio/x-m4a",
    "audio/aac",
    "audio/ogg",
    "audio/webm",
}


class UnsupportedMediaError(ValueError):
    pass


@dataclass(frozen=True, slots=True)
class Detected:
    mime: str
    kind: MediaKind
    extension: str


def _is_utf8_text(path: Path) -> bool:
    try:
        with path.open("rb") as f:
            f.read(1024 * 1024).decode("utf-8")
    except UnicodeDecodeError:
        return False
    return True


def detect(path: Path, filename: str) -> Detected:
    """Return MIME type and media kind, or raise UnsupportedMediaError (e.g. HTML, SVG,
    executables — anything that could be dangerous to serve or is not an archive format)."""
    guess = filetype.guess(str(path))
    if guess is not None:
        mime, ext = guess.mime, f".{guess.extension}"
        if mime in IMAGE_TYPES:
            return Detected(mime, MediaKind.photo, ext)
        if mime == "application/pdf":
            return Detected(mime, MediaKind.pdf, ext)
        if mime in AUDIO_TYPES:
            return Detected(mime, MediaKind.audio, ext)
        if mime in VIDEO_TYPES:
            return Detected(mime, MediaKind.video, ext)
        if mime in DOCUMENT_TYPES:
            return Detected(mime, MediaKind.other, ext)
        raise UnsupportedMediaError(mime)
    suffix = Path(filename).suffix.lower()
    if suffix in TEXT_EXTENSIONS and _is_utf8_text(path):
        return Detected("text/plain; charset=utf-8", MediaKind.other, suffix)
    raise UnsupportedMediaError("unknown")


def safe_filename(name: str, fallback_ext: str) -> str:
    """ASCII, storage-key-safe version of an uploaded file name (the original name is kept
    in the database). "Лист від Ольги 1951.JPG" → "lyst-vid-olhy-1951.jpg"."""
    p = Path(name)
    stem = transliterate_uk(p.stem)
    stem = re.sub(r"[^a-z0-9]+", "-", stem.lower()).strip("-")[:80] or "file"
    ext = re.sub(r"[^a-z0-9.]", "", p.suffix.lower())[:10] or fallback_ext
    return f"{stem}{ext}"
