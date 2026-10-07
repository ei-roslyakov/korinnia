from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest
from httpx import AsyncClient


@pytest.mark.parametrize("path", ["/healthz", "/api/healthz"])
async def test_healthz(client: AsyncClient, path: str) -> None:
    resp = await client.get(path)
    assert resp.status_code == 200
    assert resp.json() == {"status": "ok"}


async def test_readyz_ok(client: AsyncClient) -> None:
    with patch("app.api.health.ping_database", new=AsyncMock(return_value=None)):
        resp = await client.get("/readyz")
    assert resp.status_code == 200
    assert resp.json() == {"status": "ok", "checks": {"database": "ok", "storage": "ok"}}


async def test_readyz_database_down(client: AsyncClient) -> None:
    with patch("app.api.health.ping_database", new=AsyncMock(side_effect=OSError("down"))):
        resp = await client.get("/readyz")
    assert resp.status_code == 503
    assert resp.json()["checks"] == {"database": "error", "storage": "ok"}


async def test_meta(client: AsyncClient) -> None:
    resp = await client.get("/api/v1/meta")
    assert resp.status_code == 200
    body = resp.json()
    assert body["name"] == "Korinnia"
    assert body["environment"] == "test"


async def test_openapi_available_outside_production(client: AsyncClient) -> None:
    resp = await client.get("/api/openapi.json")
    assert resp.status_code == 200
