from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, Field, model_validator

from app.core.enums import Language, TreeRole
from app.schemas.common import DisplayName, Email, NewPassword, Schema


class UserOut(Schema):
    id: uuid.UUID
    email: str
    display_name: str
    preferred_language: Language
    is_superadmin: bool
    is_active: bool
    totp_enabled: bool
    created_at: datetime
    last_login_at: datetime | None


class CreateUserRequest(BaseModel):
    email: Email
    display_name: DisplayName
    password: NewPassword
    preferred_language: Language = Language.uk
    is_superadmin: bool = False


class UpdateUserRequest(BaseModel):
    display_name: DisplayName | None = None
    preferred_language: Language | None = None
    is_active: bool | None = None
    is_superadmin: bool | None = None


class LinkResponse(BaseModel):
    url: str
    expires_at: datetime


class InvitationOut(Schema):
    id: uuid.UUID
    email: str
    tree_id: uuid.UUID | None
    tree_name: str | None = None
    role: TreeRole | None
    is_superadmin: bool
    created_at: datetime
    expires_at: datetime
    accepted_at: datetime | None
    revoked_at: datetime | None
    created_by_name: str | None = None


class CreatedInvitation(BaseModel):
    invitation: InvitationOut
    url: str


class CreateInvitationRequest(BaseModel):
    email: Email
    tree_id: uuid.UUID | None = None
    role: TreeRole | None = None
    is_superadmin: bool = False

    @model_validator(mode="after")
    def _tree_and_role_together(self) -> CreateInvitationRequest:
        if (self.tree_id is None) != (self.role is None):
            raise ValueError("tree_id and role must be given together")
        if self.tree_id is None and not self.is_superadmin:
            raise ValueError("an invitation needs a tree (with role) or superadmin rights")
        return self


class UserListQuery(BaseModel):
    q: str | None = Field(default=None, max_length=200)
    is_active: bool | None = None
