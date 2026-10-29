from __future__ import annotations

import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field

from app.core.enums import LivingPrivacy, TreeRole
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
    is_demo: bool = False
    living_privacy: LivingPrivacy = LivingPrivacy.share_links
    show_living_portraits: bool = False
    # The current reader sees only the basics of living people (D114).
    living_details_hidden: bool = False
    # Overview for the tree list (only filled there).
    person_count: int = 0
    first_year: int | None = None
    last_year: int | None = None
    cover: list[str] = Field(default_factory=list)  # up to four portrait URLs


class CreateTreeRequest(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    description: str | None = Field(default=None, max_length=10_000)
    # User who becomes the tree's owner and first admin (defaults to the creator).
    owner_id: uuid.UUID | None = None


class UpdateTreeRequest(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=200)
    description: str | None = Field(default=None, max_length=10_000)
    living_privacy: LivingPrivacy | None = None
    show_living_portraits: bool | None = None


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
    # False ("share with a user"): an email without an account is an error (404
    # `no_user_with_email`) instead of creating an invitation link.
    invite: bool = True


class AddMemberResponse(BaseModel):
    kind: Literal["member", "invitation"]
    member: MemberOut | None = None
    invitation: InvitationOut | None = None
    url: str | None = None


class UpdateMemberRequest(BaseModel):
    role: TreeRole


class AdminTreeOut(BaseModel):
    """A tree as the instance admin sees it (any tree, including deleted ones)."""

    id: uuid.UUID
    name: str
    is_demo: bool
    owner_id: uuid.UUID | None
    owner_name: str | None
    owner_email: str | None
    member_count: int
    person_count: int
    created_at: datetime
    deleted_at: datetime | None
