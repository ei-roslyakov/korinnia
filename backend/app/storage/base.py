"""Storage abstraction.

Design rules (long-term preservation):
- Objects are immutable once written: `put` never overwrites an existing key unless
  `overwrite=True` is passed explicitly (only derived files such as thumbnails do that).
- Every `put` computes SHA-256 while streaming so integrity can be verified later.
- Keys are POSIX-style relative paths; traversal (`..`, absolute paths) is rejected.
"""

from __future__ import annotations

import hashlib
import re
from abc import ABC, abstractmethod
from collections.abc import AsyncIterator
from dataclasses import dataclass
from typing import BinaryIO

CHUNK_SIZE = 1024 * 1024
_KEY_RE = re.compile(r"^[A-Za-z0-9._\-/]+$")


class StorageError(Exception):
    """Base storage error."""


class ObjectNotFoundError(StorageError):
    pass


class ObjectExistsError(StorageError):
    pass


class InvalidKeyError(StorageError):
    pass


@dataclass(frozen=True, slots=True)
class StoredObject:
    key: str
    size: int
    sha256: str
    content_type: str | None = None


def validate_key(key: str) -> str:
    """Return the key if it is a safe relative path, else raise InvalidKeyError."""
    if (
        not key
        or key.startswith("/")
        or not _KEY_RE.fullmatch(key)
        or any(part in ("", ".", "..") for part in key.split("/"))
    ):
        raise InvalidKeyError(f"invalid storage key: {key!r}")
    return key


def sha256_file(fileobj: BinaryIO) -> tuple[str, int]:
    """Hash a seekable binary file from its current position; rewinds afterwards."""
    start = fileobj.tell()
    digest = hashlib.sha256()
    size = 0
    while chunk := fileobj.read(CHUNK_SIZE):
        digest.update(chunk)
        size += len(chunk)
    fileobj.seek(start)
    return digest.hexdigest(), size


class Storage(ABC):
    """Async storage interface (implemented by LocalStorage)."""

    @abstractmethod
    async def put(
        self,
        key: str,
        fileobj: BinaryIO,
        *,
        content_type: str | None = None,
        overwrite: bool = False,
    ) -> StoredObject:
        """Store the content of a seekable binary file under `key`."""

    @abstractmethod
    def open(self, key: str) -> AsyncIterator[bytes]:
        """Stream the object's bytes in chunks."""

    @abstractmethod
    async def exists(self, key: str) -> bool: ...

    @abstractmethod
    async def size(self, key: str) -> int: ...

    @abstractmethod
    async def delete(self, key: str) -> None:
        """Delete an object. Missing objects are ignored."""

    @abstractmethod
    def list_keys(self, prefix: str = "") -> AsyncIterator[str]:
        """Iterate over keys under a prefix (used by integrity checks and backups)."""

    @abstractmethod
    async def check(self) -> None:
        """Raise if the backend is not usable (readiness probe)."""

    async def sha256(self, key: str) -> str:
        """Recompute SHA-256 of a stored object (integrity verification)."""
        digest = hashlib.sha256()
        async for chunk in self.open(key):
            digest.update(chunk)
        return digest.hexdigest()

    async def read_bytes(self, key: str) -> bytes:
        return b"".join([chunk async for chunk in self.open(key)])
