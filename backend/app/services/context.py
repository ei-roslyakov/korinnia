"""Who is performing an action, and from where (for audit and throttling)."""

from __future__ import annotations

from dataclasses import dataclass

from app.models import User


@dataclass(frozen=True, slots=True)
class Actor:
    user: User | None
    ip: str | None = None
    user_agent: str | None = None

    @property
    def label(self) -> str | None:
        return self.user.email if self.user else None
