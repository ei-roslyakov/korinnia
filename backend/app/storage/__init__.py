"""File storage: originals and derived media on a local filesystem volume.

The `Storage` interface keeps the rest of the app independent of the filesystem layout.
"""

from __future__ import annotations

from functools import lru_cache

from app.core.config import get_settings
from app.storage.base import (
    InvalidKeyError,
    ObjectExistsError,
    ObjectNotFoundError,
    Storage,
    StorageError,
    StoredObject,
)
from app.storage.local import LocalStorage

__all__ = [
    "InvalidKeyError",
    "LocalStorage",
    "ObjectExistsError",
    "ObjectNotFoundError",
    "Storage",
    "StorageError",
    "StoredObject",
    "get_storage",
]


@lru_cache
def get_storage() -> Storage:
    return LocalStorage(get_settings().media_root)
