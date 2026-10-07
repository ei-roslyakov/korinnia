"""Media: upload validation, processing, serving, tagging, primary photo, trash/history."""

from __future__ import annotations

import io
import shutil
import struct
import wave
from pathlib import Path
from typing import Any

import pytest
from anyio import run_process
from PIL import Image
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import MediaFile, Person, TreeRole
from app.services.genealogy import media as media_service
from app.storage import LocalStorage
from tests.helpers import Ctx, y

HAS_FFMPEG = shutil.which("ffmpeg") is not None


def jpeg(width: int = 64, height: int = 32, orientation: int | None = None) -> bytes:
    im = Image.new("RGB", (width, height), (200, 120, 40))
    buf = io.BytesIO()
    exif = Image.Exif()
    if orientation:
        exif[0x0112] = orientation  # EXIF Orientation
    im.save(buf, "JPEG", exif=exif)
    return buf.getvalue()


def png() -> bytes:
    buf = io.BytesIO()
    Image.new("RGBA", (40, 40), (0, 128, 0, 128)).save(buf, "PNG")
    return buf.getvalue()


def wav(seconds: float = 0.5) -> bytes:
    buf = io.BytesIO()
    with wave.open(buf, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(8000)
        w.writeframes(struct.pack("<h", 0) * int(8000 * seconds))
    return buf.getvalue()


PDF = (
    b"%PDF-1.4\n1 0 obj<</Type/Catalog/Pages 2 0 R>>endobj\n"
    b"2 0 obj<</Type/Pages/Kids[3 0 R]/Count 1>>endobj\n"
    b"3 0 obj<</Type/Page/Parent 2 0 R/MediaBox[0 0 200 100]>>endobj\n"
    b"trailer<</Root 1 0 R>>\n%%EOF\n"
)


async def upload(ctx: Ctx, name: str, data: bytes, **form: Any) -> Any:
    return await ctx.editor.post(
        f"{ctx.base}/media",
        files={"file": (name, data, "application/octet-stream")},
        data={k: str(v) for k, v in form.items()},
    )


async def process(session: AsyncSession, storage: LocalStorage, media_id: str) -> None:
    import uuid

    await media_service.process_media(session, storage, uuid.UUID(media_id))


async def test_photo_upload_process_and_serve(
    ctx: Ctx, session: AsyncSession, local_storage: LocalStorage, job_queue: Any
) -> None:
    person = await ctx.person("Галина")
    data = jpeg(64, 32, orientation=6)  # stored sideways; displayed upright
    resp = await upload(
        ctx, "Галина 1946 весілля.JPG", data, person_id=person["id"], title="Весілля"
    )
    assert resp.status_code == 201, resp.text
    media = resp.json()
    assert media["kind"] == "photo"
    assert media["mime_type"] == "image/jpeg"
    assert media["processing_status"] == "pending"
    assert media["title"] == "Весілля"
    assert media["original_filename"] == "Галина 1946 весілля.JPG"
    assert media["urls"]["thumb"] is None
    assert [p["person_id"] for p in media["people"]] == [person["id"]]
    assert [j["task_name"] for j in job_queue.jobs.values()] == ["media.process", "media.avatar"]

    # The original is stored byte for byte under a readable key.
    row = await session.get(MediaFile, media["id"])
    assert row is not None
    assert row.original_key.endswith("/halyna-1946-vesillia.jpg")
    assert (local_storage.root / row.original_key).read_bytes() == data

    await process(session, local_storage, media["id"])
    media = (await ctx.editor.get(f"{ctx.base}/media/{media['id']}")).json()
    assert media["processing_status"] == "ready"
    assert (media["width"], media["height"]) == (32, 64)  # EXIF rotation applied

    original = await ctx.editor.get(media["urls"]["original"])
    assert original.content == data
    assert original.headers["content-type"] == "image/jpeg"
    assert "filename*=UTF-8''" in original.headers["content-disposition"]
    thumb = await ctx.editor.get(media["urls"]["thumb"])
    assert thumb.headers["content-type"] == "image/webp"
    assert Image.open(io.BytesIO(thumb.content)).size == (32, 64)
    web = await ctx.editor.get(media["urls"]["web"])
    assert web.headers["content-type"] == "image/webp"

    # First photo of a person becomes their portrait; the worker renders the crop.
    detail = (await ctx.editor.get(f"{ctx.base}/persons/{person['id']}")).json()
    assert detail["primary_photo_id"] == media["id"]
    assert detail["avatar_url"] == media["urls"]["thumb"]  # until the portrait exists
    assert detail["portrait_pending"] is True
    await media_service.make_avatar(session, local_storage, __import__("uuid").UUID(person["id"]))
    detail = (await ctx.editor.get(f"{ctx.base}/persons/{person['id']}")).json()
    assert "/avatar?v=" in detail["avatar_url"]
    assert detail["portrait_pending"] is False
    avatar = await ctx.editor.get(detail["avatar_url"])
    assert Image.open(io.BytesIO(avatar.content)).size == (400, 400)
    graph = (await ctx.editor.get(f"{ctx.base}/graph")).json()
    assert graph["persons"][0]["avatar_url"] == detail["avatar_url"]


async def test_x_accel_redirect(ctx: Ctx, monkeypatch: pytest.MonkeyPatch) -> None:
    from app.core.config import get_settings

    media = (await upload(ctx, "a.png", png())).json()
    monkeypatch.setattr(get_settings(), "media_x_accel", True)
    resp = await ctx.editor.get(media["urls"]["original"])
    assert resp.status_code == 200
    assert resp.content == b""
    assert resp.headers["x-accel-redirect"].startswith("/_media/originals/")
    assert resp.headers["content-type"] == "image/png"


async def test_upload_validation(ctx: Ctx, monkeypatch: pytest.MonkeyPatch) -> None:
    for name, data in [
        ("page.html", b"<!doctype html><html><script>alert(1)</script></html>"),
        ("logo.svg", b'<svg xmlns="http://www.w3.org/2000/svg"><script/></svg>'),
        ("tool.exe", b"MZ\x90\x00" + b"\x00" * 100),
        ("notes.txt", b"\xff\xfe\x00binary"),
    ]:
        resp = await upload(ctx, name, data)
        assert resp.status_code == 415, name
        assert resp.json()["code"] == "unsupported_media_type"
    resp = await upload(ctx, "empty.jpg", b"")
    assert resp.json()["code"] == "empty_file"

    text = await upload(ctx, "лист.txt", "Дорога Галю!".encode())
    assert text.status_code == 201
    assert text.json()["kind"] == "other"

    from app.core.config import get_settings

    monkeypatch.setattr(get_settings(), "max_upload_size_mb", 0)
    resp = await upload(ctx, "big.png", png())
    assert resp.status_code == 413
    assert resp.json()["code"] == "file_too_large"


async def test_duplicates_and_kinds(ctx: Ctx) -> None:
    data = png()
    first = (await upload(ctx, "scan.png", data, kind="document_scan")).json()
    assert first["kind"] == "document_scan"
    resp = await upload(ctx, "same.png", data)
    assert resp.status_code == 409
    assert resp.json()["code"] == "duplicate_media"
    assert resp.json()["media_id"] == first["id"]
    assert (await upload(ctx, "same.png", data, allow_duplicate="true")).status_code == 201

    pdf = (await upload(ctx, "довідка.pdf", PDF)).json()
    assert pdf["kind"] == "pdf"
    resp = await ctx.editor.patch(f"{ctx.base}/media/{pdf['id']}", json={"kind": "photo"})
    assert resp.json()["code"] == "invalid_media_kind"
    resp = await ctx.editor.patch(f"{ctx.base}/media/{first['id']}", json={"kind": "photo"})
    assert resp.json()["kind"] == "photo"


async def test_pdf_and_audio_processing(
    ctx: Ctx, session: AsyncSession, local_storage: LocalStorage
) -> None:
    pdf = (await upload(ctx, "doc.pdf", PDF)).json()
    await process(session, local_storage, pdf["id"])
    pdf = (await ctx.editor.get(f"{ctx.base}/media/{pdf['id']}")).json()
    assert pdf["processing_status"] == "ready"
    if shutil.which("pdftoppm"):
        assert pdf["urls"]["thumb"]
    else:
        assert "pdftoppm" in pdf["processing_error"]
    assert (await ctx.editor.get(pdf["urls"]["web"])).headers["content-type"] == "application/pdf"

    audio = (await upload(ctx, "бабуся-розповідає.wav", wav())).json()
    assert audio["kind"] == "audio"
    await process(session, local_storage, audio["id"])
    audio = (await ctx.editor.get(f"{ctx.base}/media/{audio['id']}")).json()
    assert audio["processing_status"] == "ready"
    if HAS_FFMPEG:
        assert audio["duration_seconds"] == pytest.approx(0.5, abs=0.1)
        web = await ctx.editor.get(audio["urls"]["web"])
        assert web.headers["content-type"] == "audio/mpeg"  # WAV → MP3 for browsers
    assert (await ctx.editor.get(f"{ctx.base}/media/{audio['id']}/file/thumb")).status_code == 404


@pytest.mark.skipif(not HAS_FFMPEG, reason="ffmpeg not installed")
async def test_video_processing(
    ctx: Ctx, session: AsyncSession, local_storage: LocalStorage, tmp_path: Path
) -> None:
    src = tmp_path / "clip.mov"
    await run_process(
        ["ffmpeg", "-v", "error", "-f", "lavfi", "-i", "testsrc=duration=1:size=320x240:rate=10",
         "-c:v", "mpeg4", str(src)],
    )  # fmt: skip
    video = (await upload(ctx, "Весілля 1975.mov", src.read_bytes())).json()
    assert video["kind"] == "video"
    await process(session, local_storage, video["id"])
    video = (await ctx.editor.get(f"{ctx.base}/media/{video['id']}")).json()
    assert video["processing_status"] == "ready", video["processing_error"]
    assert (video["width"], video["height"]) == (320, 240)
    assert video["duration_seconds"] == pytest.approx(1.0, abs=0.2)
    web = await ctx.editor.get(video["urls"]["web"])
    assert web.headers["content-type"] == "video/mp4"
    assert (await ctx.editor.get(video["urls"]["thumb"])).headers["content-type"] == "image/webp"


async def test_processing_failure_is_recorded(
    ctx: Ctx, session: AsyncSession, local_storage: LocalStorage
) -> None:
    media = (await upload(ctx, "broken.jpg", jpeg()[:200])).json()  # truncated JPEG
    await process(session, local_storage, media["id"])
    media = (await ctx.editor.get(f"{ctx.base}/media/{media['id']}")).json()
    assert media["processing_status"] == "failed"
    assert media["processing_error"]
    # The original is still downloadable, and reprocessing can be requested.
    assert (await ctx.editor.get(media["urls"]["original"])).status_code == 200
    resp = await ctx.editor.post(f"{ctx.base}/media/{media['id']}/reprocess")
    assert resp.status_code == 200


async def test_tags_regions_order_and_primary(ctx: Ctx, session: AsyncSession) -> None:
    a, b = await ctx.person("Олександр"), await ctx.person("Галина")
    group = (await upload(ctx, "group.jpg", jpeg(100, 80))).json()
    other = (await upload(ctx, "other.png", png())).json()
    base = f"{ctx.base}/media/{group['id']}/people"

    region = {"x": 0.1, "y": 0.2, "w": 0.3, "h": 0.4}
    resp = await ctx.editor.post(base, json={"person_id": a["id"], "region": region})
    assert resp.json()["people"][0]["region"] == region
    bad = await ctx.editor.post(
        base, json={"person_id": b["id"], "region": {"x": 0.9, "y": 0, "w": 0.5, "h": 0.5}}
    )
    assert bad.status_code == 422
    await ctx.editor.post(base, json={"person_id": b["id"]})
    resp = await ctx.editor.patch(
        f"{base}/{b['id']}", json={"region": {"x": 0.5, "y": 0.1, "w": 0.2, "h": 0.2}}
    )
    assert {p["person_id"] for p in resp.json()["people"]} == {a["id"], b["id"]}

    await ctx.editor.post(f"{ctx.base}/media/{other['id']}/people", json={"person_id": a["id"]})
    listing = (await ctx.editor.get(f"{ctx.base}/media", params={"person_id": a["id"]})).json()
    assert [m["id"] for m in listing["items"]] == [group["id"], other["id"]]
    resp = await ctx.editor.put(
        f"{ctx.base}/persons/{a['id']}/media-order", json={"media_ids": [other["id"], group["id"]]}
    )
    assert resp.status_code == 204
    detail = (await ctx.editor.get(f"{ctx.base}/persons/{a['id']}")).json()
    assert [m["id"] for m in detail["media"]] == [other["id"], group["id"]]
    resp = await ctx.editor.put(
        f"{ctx.base}/persons/{b['id']}/media-order", json={"media_ids": [other["id"]]}
    )
    assert resp.json()["code"] == "media_not_linked"

    # Primary photo with crop; untagging clears it.
    crop = {"x": 0.1, "y": 0.2, "w": 0.3, "h": 0.375}
    resp = await ctx.editor.patch(
        f"{ctx.base}/persons/{b['id']}",
        json={"primary_photo_id": group["id"], "primary_photo_crop": crop},
    )
    assert resp.json()["primary_photo_id"] == group["id"]
    assert resp.json()["primary_photo_crop"] == crop
    pdf = (await upload(ctx, "x.pdf", PDF)).json()
    resp = await ctx.editor.patch(
        f"{ctx.base}/persons/{b['id']}", json={"primary_photo_id": pdf["id"]}
    )
    assert resp.json()["code"] == "not_a_photo"
    resp = await ctx.editor.delete(f"{base}/{b['id']}")
    assert resp.status_code == 200
    person = await session.get(Person, b["id"])
    await session.refresh(person)
    assert person is not None
    assert person.primary_photo_id is None
    assert (await ctx.editor.delete(f"{base}/{b['id']}")).json()["code"] == "tag_not_found"
    resp = await ctx.editor.patch(f"{ctx.base}/persons/{a['id']}", json={"primary_photo_id": None})
    assert resp.json()["primary_photo_id"] is None


async def test_media_metadata_history_and_trash(ctx: Ctx) -> None:
    place = await ctx.place("Львів")
    p = await ctx.person("Галина")
    media = (await upload(ctx, "a.png", png(), person_id=p["id"])).json()
    url = f"{ctx.base}/media/{media['id']}"
    resp = await ctx.editor.patch(
        url,
        json={
            "title": "Біля оперного",
            "description": "Літо",
            "date": y(1958, precision="approx"),
            "place_id": place["id"],
        },
    )
    body = resp.json()
    assert body["date"]["text"] == "abt 1958"
    assert body["place"]["name"] == "Львів"
    listing = (await ctx.editor.get(f"{ctx.base}/media", params={"q": "оперн"})).json()
    assert listing["total"] == 1
    assert (await ctx.editor.get(f"{ctx.base}/media", params={"kind": "video"})).json()[
        "total"
    ] == 0

    history = (
        await ctx.editor.get(
            f"{ctx.base}/history", params={"entity_type": "media", "entity_id": media["id"]}
        )
    ).json()
    assert [e["action"] for e in history["items"]] == ["media.update", "media.create"]
    await ctx.editor.post(f"{ctx.base}/history/{history['items'][1]['id']}/restore")
    assert (await ctx.editor.get(url)).json()["title"] is None

    assert (await ctx.editor.delete(url)).status_code == 204
    assert (await ctx.editor.get(url)).status_code == 404
    assert (await ctx.editor.get(media["urls"]["original"])).status_code == 404
    detail = (await ctx.editor.get(f"{ctx.base}/persons/{p['id']}")).json()
    assert detail["media"] == []
    trash = (await ctx.editor.get(f"{ctx.base}/trash")).json()
    assert [(t["entity_type"], t["label"]) for t in trash] == [("media", "a.png")]
    await ctx.editor.post(f"{ctx.base}/trash/media/{media['id']}/restore")
    assert (await ctx.editor.get(url)).status_code == 200


async def test_media_permissions(
    ctx: Ctx, make_user: Any, make_client: Any, add_member: Any
) -> None:
    media = (await upload(ctx, "a.png", png())).json()
    viewer = await make_user("viewer@example.com")
    await add_member(ctx.tree, viewer, TreeRole.viewer)
    await make_user("out@example.com")
    v, o = await make_client(), await make_client()
    await v.login("viewer@example.com")
    await o.login("out@example.com")
    assert (await v.get(media["urls"]["original"])).status_code == 200
    assert (await o.get(media["urls"]["original"])).status_code == 404
    resp = await v.post(f"{ctx.base}/media", files={"file": ("b.png", png(), "image/png")})
    assert resp.status_code == 403
    assert (await v.delete(f"{ctx.base}/media/{media['id']}")).status_code == 403


async def test_job_wrappers(
    ctx: Ctx,
    session: AsyncSession,
    local_storage: LocalStorage,
    monkeypatch: pytest.MonkeyPatch,
    job_queue: Any,
) -> None:
    from contextlib import asynccontextmanager
    from datetime import timedelta

    from app.jobs import tasks

    @asynccontextmanager
    async def factory() -> Any:
        yield session

    monkeypatch.setattr(tasks, "get_sessionmaker", lambda: factory)
    monkeypatch.setattr(tasks, "get_storage", lambda: local_storage)
    person = await ctx.person("П")
    media = (await upload(ctx, "a.jpg", jpeg(), person_id=person["id"])).json()
    await tasks.process_media_file(media_id=media["id"])
    await tasks.make_person_avatar(person_id=person["id"])
    row = await session.get(Person, person["id"])
    assert row is not None
    assert row.avatar_key

    stuck = (await upload(ctx, "b.png", png())).json()
    item = await session.get(MediaFile, stuck["id"])
    assert item is not None
    item.created_at = item.created_at - timedelta(hours=1)
    await session.commit()
    job_queue.jobs.clear()
    await tasks.requeue_stuck_media(timestamp=0)
    assert [j["args"] for j in job_queue.jobs.values()] == [{"media_id": stuck["id"]}]
