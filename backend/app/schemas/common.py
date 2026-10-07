from __future__ import annotations

from typing import Annotated

from pydantic import AfterValidator, BaseModel, ConfigDict, EmailStr, Field

from app.core.config import get_settings


class Schema(BaseModel):
    model_config = ConfigDict(from_attributes=True)


def _normalize_email(value: str) -> str:
    return value.strip().lower()


def _check_password(value: str) -> str:
    min_len = get_settings().password_min_length
    if len(value) < min_len:
        raise ValueError(f"password must be at least {min_len} characters")
    return value


Email = Annotated[EmailStr, AfterValidator(_normalize_email)]
NewPassword = Annotated[str, Field(max_length=256), AfterValidator(_check_password)]
DisplayName = Annotated[str, Field(min_length=1, max_length=200)]


class Page[T](BaseModel):
    items: list[T]
    total: int
    limit: int
    offset: int
