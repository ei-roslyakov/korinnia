from __future__ import annotations

import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field

from app.models.enums import TreeRole
from app.schemas.common import Email, Schema
from app.schemas.users import InvitationOut


class TreeOut(Schema):
    id: uuid.UUID
    name: str
    description: str | None
    owner_id: uuid.UUID | None
    created_at: datetime
    updated_at: datetime
    my_role: TreeRole


class CreateTreeRequest(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    description: str | None = Field(default=None, max_length=10_000)
    # User who becomes the tree's owner and first admin (defaults to the creator).
    owner_id: uuid.UUID | None = None


class UpdateTreeRequest(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=200)
    description: str | None = Field(default=None, max_length=10_000)


class MemberOut(BaseModel):
    user_id: uuid.UUID
    email: str
    display_name: str
    role: TreeRole
    is_active: bool
    created_at: datetime


class MembersResponse(BaseModel):
    members: list[MemberOut]
    invitations: list[InvitationOut]


class AddMemberRequest(BaseModel):
    email: Email
    role: TreeRole


class AddMemberResponse(BaseModel):
    kind: Literal["member", "invitation"]
    member: MemberOut | None = None
    invitation: InvitationOut | None = None
    url: str | None = None


class UpdateMemberRequest(BaseModel):
    role: TreeRole
