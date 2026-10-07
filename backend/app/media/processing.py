"""Derivative generation. Originals are only ever read, never modified.

- photos / scans: EXIF-rotated web version (≤2048 px, WebP) + thumbnail (≤480 px, WebP)
- video: poster thumbnail + browser-friendly MP4 (H.264/AAC, ≤1280 px wide, faststart)
- audio: MP3 web version when the original is not playable in browsers (WAV, FLAC, AMR…)
- PDF: thumbnail of the first page (poppler `pdftoppm`)
- portraits: square crop of the primary photo (WebP 400×400)
"""

from __future__ import annotations

import io
import json
import logging
import shutil
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from anyio import run_process, to_thread
from PIL import Image, ImageOps
from pillow_heif import register_heif_opener

register_heif_opener()  # iPhone photos (HEIC/HEIF)
Image.MAX_IMAGE_PIXELS = 400_000_000  # large archival scans are expected

logger = logging.getLogger(__name__)

WEB_MAX = 2048
THUMB_MAX = 480
AVATAR_SIZE = 400


@dataclass
class Derivatives:
    """Generated files (name → bytes) and facts about the original."""

    files: dict[str, bytes] = field(default_factory=dict)
    width: int | None = None
    height: int | None = None
    duration: float | None = None
    note: str | None = None


def _webp(im: Image.Image, max_side: int, quality: int) -> bytes:
    copy = im.copy()
    copy.thumbnail((max_side, max_side), Image.Resampling.LANCZOS)
    if copy.mode not in ("RGB", "RGBA"):
        copy = copy.convert("RGBA" if "A" in copy.getbands() else "RGB")
    buf = io.BytesIO()
    copy.save(buf, "WEBP", quality=quality, method=4)
    return buf.getvalue()


def _open_upright(path: Path) -> Image.Image:
    im = Image.open(path)
    im.seek(0)  # first frame of GIF / multi-page TIFF
    return ImageOps.exif_transpose(im)


def image_derivatives(path: Path) -> Derivatives:
    with _open_upright(path) as im:
        return Derivatives(
            files={"web.webp": _webp(im, WEB_MAX, 82), "thumb.webp": _webp(im, THUMB_MAX, 75)},
            width=im.width,
            height=im.height,
        )


def thumb_from_image_bytes(data: bytes) -> bytes:
    with Image.open(io.BytesIO(data)) as im:
        return _webp(im, THUMB_MAX, 75)


def avatar(path: Path, crop: dict[str, float] | None) -> bytes:
    """Square portrait from the (upright) original; `crop` in 0..1 fractions."""
    with _open_upright(path) as im:
        if crop:
            box = (
                round(crop["x"] * im.width),
                round(crop["y"] * im.height),
                round((crop["x"] + crop["w"]) * im.width),
                round((crop["y"] + crop["h"]) * im.height),
            )
            region = im.crop(box)
        else:
            region = ImageOps.fit(im, (min(im.size),) * 2)  # centred square
        region = region.resize((AVATAR_SIZE, AVATAR_SIZE), Image.Resampling.LANCZOS)
        if region.mode not in ("RGB", "RGBA"):
            region = region.convert("RGB")
        buf = io.BytesIO()
        region.save(buf, "WEBP", quality=85)
        return buf.getvalue()


def have(binary: str) -> bool:
    return shutil.which(binary) is not None


async def _run(*cmd: str) -> bytes:
    result = await run_process(list(cmd), check=True)
    return bytes(result.stdout)


async def probe_duration(path: Path) -> float | None:
    if not have("ffprobe"):
        return None
    out = await _run("ffprobe", "-v", "error", "-print_format", "json", "-show_format", str(path))
    data: dict[str, Any] = json.loads(out or b"{}")
    value = data.get("format", {}).get("duration")
    return float(value) if value else None


async def video_derivatives(path: Path, workdir: Path) -> Derivatives:
    if not have("ffmpeg"):
        return Derivatives(note="ffmpeg not installed: no video preview")
    poster = workdir / "poster.jpg"
    web = workdir / "web.mp4"
    duration = await probe_duration(path)
    seek = "1" if (duration or 0) > 2 else "0"
    await _run(
        "ffmpeg", "-y", "-v", "error", "-ss", seek, "-i", str(path), "-frames:v", "1", str(poster)
    )
    await _run(
        "ffmpeg", "-y", "-v", "error", "-i", str(path),
        "-vf", "scale='min(1280,iw)':-2", "-c:v", "libx264", "-preset", "veryfast", "-crf", "26",
        "-pix_fmt", "yuv420p", "-c:a", "aac", "-b:a", "128k", "-movflags", "+faststart", str(web),
    )  # fmt: skip
    with Image.open(poster) as im:
        width, height = im.size
    return Derivatives(
        files={
            "web.mp4": web.read_bytes(),
            "thumb.webp": await to_thread.run_sync(thumb_from_image_bytes, poster.read_bytes()),
        },
        width=width,
        height=height,
        duration=duration,
    )


async def audio_derivatives(path: Path, workdir: Path, browser_playable: bool) -> Derivatives:
    duration = await probe_duration(path)
    if browser_playable:
        return Derivatives(duration=duration)
    if not have("ffmpeg"):
        return Derivatives(duration=duration, note="ffmpeg not installed: original only")
    web = workdir / "web.mp3"
    await _run(
        "ffmpeg",
        "-y",
        "-v",
        "error",
        "-i",
        str(path),
        "-vn",
        "-c:a",
        "libmp3lame",
        "-b:a",
        "160k",
        str(web),
    )
    return Derivatives(files={"web.mp3": web.read_bytes()}, duration=duration)


async def pdf_derivatives(path: Path, workdir: Path) -> Derivatives:
    if not have("pdftoppm"):
        return Derivatives(note="pdftoppm not installed: no PDF preview")
    out_prefix = workdir / "page"
    await _run(
        "pdftoppm",
        "-f",
        "1",
        "-l",
        "1",
        "-r",
        "60",
        "-png",
        "-singlefile",
        str(path),
        str(out_prefix),
    )
    png = workdir / "page.png"
    return Derivatives(
        files={"thumb.webp": await to_thread.run_sync(thumb_from_image_bytes, png.read_bytes())}
    )
