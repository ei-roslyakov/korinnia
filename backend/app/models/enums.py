"""Enumerations stored as text + CHECK constraint (not native PG enums: easier to evolve)."""

from __future__ import annotations

from enum import StrEnum


class TreeRole(StrEnum):
    viewer = "viewer"
    contributor = "contributor"
    editor = "editor"
    admin = "admin"

    @property
    def rank(self) -> int:
        return _ROLE_RANK[self]

    def at_least(self, other: TreeRole) -> bool:
        return self.rank >= other.rank


_ROLE_RANK = {
    TreeRole.viewer: 10,
    TreeRole.contributor: 20,
    TreeRole.editor: 30,
    TreeRole.admin: 40,
}


class Language(StrEnum):
    uk = "uk"
    en = "en"
    pl = "pl"
