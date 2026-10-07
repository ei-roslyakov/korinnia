from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import TYPE_CHECKING, Any

import pyotp

if TYPE_CHECKING:
    from httpx import AsyncClient as ApiClient

    from app.models import Tree


def totp_code(secret: str, steps_ahead: int = 0) -> str:
    """A valid TOTP code. Use different `steps_ahead` (0 or 1) for consecutive uses within
    one test, since a code (time-step) can only be used once."""
    return pyotp.TOTP(secret).at(datetime.now(UTC) + timedelta(seconds=30 * steps_ahead))


def y(year: int, **kw: Any) -> dict[str, Any]:
    return {"year": year, **kw}


@dataclass
class Ctx:
    tree: Tree
    editor: ApiClient
    base: str

    async def person(self, first: str, last: str = "Коваленко", **extra: Any) -> dict[str, Any]:
        body = {"names": [{"first_name": first, "last_name": last}], **extra}
        resp = await self.editor.post(f"{self.base}/persons", json=body)
        assert resp.status_code == 201, resp.text
        return resp.json()  # type: ignore[no-any-return]

    async def link(self, parent: str, child: str, type_: str = "biological") -> dict[str, Any]:
        resp = await self.editor.post(
            f"{self.base}/parent-child",
            json={"parent_id": parent, "child_id": child, "type": type_},
        )
        assert resp.status_code == 201, resp.text
        return resp.json()  # type: ignore[no-any-return]

    async def place(self, name: str, **extra: Any) -> dict[str, Any]:
        resp = await self.editor.post(f"{self.base}/places", json={"name": name, **extra})
        assert resp.status_code == 201, resp.text
        return resp.json()  # type: ignore[no-any-return]
