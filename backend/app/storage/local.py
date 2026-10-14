"""Local filesystem storage.

Files are stored as plain files under `root/<key>` — readable without the application.
Writes are atomic (temp file + rename) and fsync'ed.
"""

from __future__ import annotations

import contextlib
import os
import shutil
import tempfile
from collections.abc import AsyncIterator
from pathlib import Path
from typing import BinaryIO

import anyio
from anyio import to_thread

from app.storage.base import (
    CHUNK_SIZE,
    ObjectExistsError,
    ObjectNotFoundError,
    Storage,
    StorageError,
    StoredObject,
    sha256_file,
    validate_key,
)

FILE_MODE = 0o644


class LocalStorage(Storage):
    def __init__(self, root: Path) -> None:
        self.root = root.resolve()

    def path(self, key: str) -> Path:
        """Filesystem path of an object (for serving files without copying them)."""
        return self._path(key)

    def _path(self, key: str) -> Path:
        path = (self.root / validate_key(key)).resolve()
        if not path.is_relative_to(self.root):  # defence in depth against traversal
            raise StorageError(f"key escapes storage root: {key!r}")
        return path

    def _put_sync(self, key: str, fileobj: BinaryIO, overwrite: bool) -> tuple[str, int]:
        dest = self._path(key)
        if dest.exists() and not overwrite:
            raise ObjectExistsError(key)
        dest.parent.mkdir(parents=True, exist_ok=True)
        digest, size = sha256_file(fileobj)
        fd, tmp_name = tempfile.mkstemp(dir=dest.parent, prefix=".upload-")
        try:
            with os.fdopen(fd, "wb") as tmp:
                shutil.copyfileobj(fileobj, tmp, CHUNK_SIZE)
                tmp.flush()
                os.fsync(tmp.fileno())
            # mkstemp creates 0600 files; nginx (another user) serves them via X-Accel-
            # Redirect after the API checked permissions, so they must be readable.
            os.chmod(tmp_name, FILE_MODE)
            os.replace(tmp_name, dest)
        except BaseException:
            Path(tmp_name).unlink(missing_ok=True)
            raise
        return digest, size

    async def put(
        self,
        key: str,
        fileobj: BinaryIO,
        *,
        content_type: str | None = None,
        overwrite: bool = False,
    ) -> StoredObject:
        digest, size = await to_thread.run_sync(self._put_sync, key, fileobj, overwrite)
        return StoredObject(key=key, size=size, sha256=digest, content_type=content_type)

    async def open(self, key: str) -> AsyncIterator[bytes]:
        path = self._path(key)
        if not path.is_file():
            raise ObjectNotFoundError(key)
        async with await anyio.open_file(path, "rb") as f:
            while chunk := await f.read(CHUNK_SIZE):
                yield chunk

    async def exists(self, key: str) -> bool:
        return self._path(key).is_file()

    async def size(self, key: str) -> int:
        path = self._path(key)
        if not path.is_file():
            raise ObjectNotFoundError(key)
        return path.stat().st_size

    async def delete(self, key: str) -> None:
        self._path(key).unlink(missing_ok=True)

    async def delete_prefix(self, prefix: str) -> int:
        count = await super().delete_prefix(prefix)
        base = self._path(prefix.rstrip("/"))
        if base.is_dir():
            # Remove the emptied folders too (deepest first).
            dirs = sorted((p for p in base.rglob("*") if p.is_dir()), key=lambda p: -len(p.parts))
            for d in [*dirs, base]:
                # Not empty: something was added meanwhile.
                with contextlib.suppress(OSError):
                    d.rmdir()
        return count

    async def list_keys(self, prefix: str = "") -> AsyncIterator[str]:
        base = self.root / prefix if prefix else self.root
        if not base.exists():
            return
        paths = await to_thread.run_sync(lambda: sorted(p for p in base.rglob("*") if p.is_file()))
        for path in paths:
            if path.name.startswith(".upload-"):
                continue
            yield path.relative_to(self.root).as_posix()

    async def check(self) -> None:
        def _check() -> None:
            self.root.mkdir(parents=True, exist_ok=True)
            if not os.access(self.root, os.W_OK):
                raise StorageError(f"storage root not writable: {self.root}")

        await to_thread.run_sync(_check)
