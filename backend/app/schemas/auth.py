from __future__ import annotations

import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field

from app.models.enums import Language, TreeRole
from app.schemas.common import DisplayName, Email, NewPassword, Schema


class LoginRequest(BaseModel):
    email: Email
    password: str = Field(max_length=256)


class MfaRequest(BaseModel):
    code: str = Field(min_length=6, max_length=20, description="TOTP code or recovery code")


class MeTree(Schema):
    id: uuid.UUID
    name: str
    role: TreeRole


class Me(Schema):
    id: uuid.UUID
    email: str
    display_name: str
    preferred_language: Language
    is_superadmin: bool
    totp_enabled: bool
    trees: list[MeTree]


class LoginResponse(BaseModel):
    status: Literal["ok", "mfa_required"]
    user: Me | None = None


class CsrfResponse(BaseModel):
    csrf_token: str


class UpdateMeRequest(BaseModel):
    display_name: DisplayName | None = None
    preferred_language: Language | None = None


class ChangePasswordRequest(BaseModel):
    current_password: str = Field(max_length=256)
    new_password: NewPassword


class TotpSetupResponse(BaseModel):
    secret: str
    otpauth_uri: str
    qr_svg: str


class TotpEnableRequest(BaseModel):
    code: str = Field(min_length=6, max_length=10)


class TotpDisableRequest(BaseModel):
    password: str = Field(max_length=256)
    code: str = Field(min_length=6, max_length=20)


class RecoveryCodesResponse(BaseModel):
    recovery_codes: list[str]


class InvitationInfo(BaseModel):
    email: str
    tree_name: str | None
    role: TreeRole | None
    is_superadmin: bool
    expires_at: datetime


class AcceptInvitationRequest(BaseModel):
    display_name: DisplayName
    password: NewPassword
    preferred_language: Language = Language.uk


class PasswordResetInfo(BaseModel):
    email: str
    expires_at: datetime


class PasswordResetRequest(BaseModel):
    password: NewPassword
