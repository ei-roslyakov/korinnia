from __future__ import annotations

import os
from collections.abc import AsyncIterator, Iterator
from pathlib import Path

import pytest
from httpx import ASGITransport, AsyncClient

os.environ["ENVIRONMENT"] = "test"

from app.core.config import get_settings
from app.main import create_app
from app.storage import LocalStorage, get_storage


@pytest.fixture
def local_storage(tmp_path: Path) -> LocalStorage:
    return LocalStorage(tmp_path / "media")


@pytest.fixture
def app(local_storage: LocalStorage) -> Iterator[object]:
    get_settings.cache_clear()
    application = create_app()
    application.dependency_overrides[get_storage] = lambda: local_storage
    yield application
    application.dependency_overrides.clear()


@pytest.fixture
async def client(app: object) -> AsyncIterator[AsyncClient]:
    transport = ASGITransport(app=app)  # type: ignore[arg-type]
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac
