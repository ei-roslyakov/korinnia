from __future__ import annotations

import hashlib
import io
import os
from pathlib import Path

import pytest

from app.core.config import Settings, get_settings
from app.storage import (
    InvalidKeyError,
    LocalStorage,
    ObjectExistsError,
    ObjectNotFoundError,
    StorageError,
    get_storage,
)


async def test_put_and_read_roundtrip(local_storage: LocalStorage) -> None:
    data = b"family photo bytes" * 1000
    stored = await local_storage.put(
        "originals/a/photo.jpg", io.BytesIO(data), content_type="image/jpeg"
    )
    assert stored.size == len(data)
    assert stored.sha256 == hashlib.sha256(data).hexdigest()
    assert await local_storage.exists("originals/a/photo.jpg")
    assert await local_storage.size("originals/a/photo.jpg") == len(data)
    assert await local_storage.read_bytes("originals/a/photo.jpg") == data
    assert await local_storage.sha256("originals/a/photo.jpg") == stored.sha256


async def test_files_are_plain_files_on_disk(local_storage: LocalStorage) -> None:
    """Archive must be readable without the app: key == relative path on disk."""
    await local_storage.put("originals/x/letter.pdf", io.BytesIO(b"%PDF"))
    assert (local_storage.root / "originals/x/letter.pdf").read_bytes() == b"%PDF"
    assert not list(local_storage.root.rglob(".upload-*"))


async def test_originals_are_never_overwritten(local_storage: LocalStorage) -> None:
    await local_storage.put("k/file.bin", io.BytesIO(b"one"))
    with pytest.raises(ObjectExistsError):
        await local_storage.put("k/file.bin", io.BytesIO(b"two"))
    assert await local_storage.read_bytes("k/file.bin") == b"one"
    await local_storage.put("k/file.bin", io.BytesIO(b"two"), overwrite=True)
    assert await local_storage.read_bytes("k/file.bin") == b"two"


async def test_failed_write_leaves_no_partial_file(local_storage: LocalStorage) -> None:
    class Broken(io.BytesIO):
        calls = 0

        def read(self, size: int | None = -1) -> bytes:
            self.calls += 1
            if self.calls > 2:  # first pass (hashing) succeeds, copy fails
                raise OSError("disk error")
            return super().read(size)

    with pytest.raises(OSError, match="disk error"):
        await local_storage.put("k/broken.bin", Broken(b"data"))
    assert not await local_storage.exists("k/broken.bin")
    assert not list(local_storage.root.rglob(".upload-*"))


async def test_missing_object(local_storage: LocalStorage) -> None:
    assert not await local_storage.exists("nope/x.bin")
    with pytest.raises(ObjectNotFoundError):
        await local_storage.read_bytes("nope/x.bin")
    with pytest.raises(ObjectNotFoundError):
        await local_storage.size("nope/x.bin")
    await local_storage.delete("nope/x.bin")  # idempotent


async def test_delete_and_list(local_storage: LocalStorage) -> None:
    for key in ("a/1.txt", "a/2.txt", "b/3.txt"):
        await local_storage.put(key, io.BytesIO(key.encode()))
    assert [k async for k in local_storage.list_keys("a")] == ["a/1.txt", "a/2.txt"]
    await local_storage.delete("a/1.txt")
    assert [k async for k in local_storage.list_keys()] == ["a/2.txt", "b/3.txt"]
    assert [k async for k in local_storage.list_keys("missing")] == []


async def test_check_creates_root(tmp_path: Path) -> None:
    storage = LocalStorage(tmp_path / "new" / "media")
    await storage.check()
    assert storage.root.is_dir()


@pytest.mark.skipif(os.geteuid() == 0, reason="root bypasses permissions")
async def test_check_fails_when_read_only(tmp_path: Path) -> None:
    root = tmp_path / "ro"
    root.mkdir()
    root.chmod(0o500)
    try:
        with pytest.raises(StorageError):
            await LocalStorage(root).check()
    finally:
        root.chmod(0o700)


@pytest.mark.parametrize(
    "key", ["", "/etc/passwd", "../escape", "a/../../b", "a//b", "a/./b", "with space", "ü.jpg"]
)
async def test_invalid_keys_rejected(local_storage: LocalStorage, key: str) -> None:
    with pytest.raises(InvalidKeyError):
        await local_storage.put(key, io.BytesIO(b"x"))


async def test_symlink_escape_rejected(local_storage: LocalStorage, tmp_path: Path) -> None:
    outside = tmp_path / "outside"
    outside.mkdir()
    local_storage.root.mkdir(parents=True)
    (local_storage.root / "link").symlink_to(outside)
    with pytest.raises(StorageError):
        await local_storage.put("link/evil.txt", io.BytesIO(b"x"))


def test_get_storage_uses_media_root(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("MEDIA_ROOT", str(tmp_path))
    get_settings.cache_clear()
    get_storage.cache_clear()
    try:
        storage = get_storage()
        assert isinstance(storage, LocalStorage)
        assert storage.root == tmp_path.resolve()
        assert Settings().media_root == tmp_path
    finally:
        get_settings.cache_clear()
        get_storage.cache_clear()
