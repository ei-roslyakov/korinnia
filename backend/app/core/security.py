"""Low-level security primitives: password hashing, JWTs, one-time tokens, TOTP."""

from __future__ import annotations

import hashlib
import hmac
import secrets
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any, Literal

import jwt
import pyotp
import segno
from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerificationError, VerifyMismatchError

from app.core.config import get_settings

JWT_ALGORITHM = "HS256"
TokenType = Literal["access", "refresh", "mfa"]

# argon2id with library defaults (RFC 9106 "low memory" profile).
_hasher = PasswordHasher()
# Verified against when the email is unknown, so response time doesn't reveal which emails exist.
_DUMMY_HASH = _hasher.hash("korinnia-dummy-password")


def utcnow() -> datetime:
    return datetime.now(UTC)


# --- Passwords --------------------------------------------------------------------------


def hash_password(password: str) -> str:
    return _hasher.hash(password)


def verify_password(password: str, password_hash: str | None) -> bool:
    try:
        return _hasher.verify(password_hash or _DUMMY_HASH, password) and password_hash is not None
    except (VerifyMismatchError, VerificationError, InvalidHashError):
        return False


def password_needs_rehash(password_hash: str) -> bool:
    return _hasher.check_needs_rehash(password_hash)


# --- JWT --------------------------------------------------------------------------------


class TokenError(Exception):
    def __init__(self, code: str) -> None:
        super().__init__(code)
        self.code = code


@dataclass(frozen=True, slots=True)
class TokenPayload:
    sub: uuid.UUID
    type: TokenType
    iat: datetime
    exp: datetime
    jti: uuid.UUID | None = None
    fam: uuid.UUID | None = None


def _secret() -> str:
    return get_settings().secret_key.get_secret_value()


def create_token(
    user_id: uuid.UUID,
    token_type: TokenType,
    ttl: timedelta,
    *,
    jti: uuid.UUID | None = None,
    family_id: uuid.UUID | None = None,
    now: datetime | None = None,
) -> str:
    issued = (now or utcnow()).replace(microsecond=0)
    claims: dict[str, Any] = {
        "sub": str(user_id),
        "type": token_type,
        "iat": int(issued.timestamp()),
        "exp": int((issued + ttl).timestamp()),
    }
    if jti:
        claims["jti"] = str(jti)
    if family_id:
        claims["fam"] = str(family_id)
    return jwt.encode(claims, _secret(), algorithm=JWT_ALGORITHM)


def decode_token(token: str, expected_type: TokenType) -> TokenPayload:
    try:
        claims = jwt.decode(
            token,
            _secret(),
            algorithms=[JWT_ALGORITHM],
            options={"require": ["sub", "type", "iat", "exp"]},
        )
    except jwt.ExpiredSignatureError as exc:
        raise TokenError("token_expired") from exc
    except jwt.InvalidTokenError as exc:
        raise TokenError("token_invalid") from exc
    if claims.get("type") != expected_type:
        raise TokenError("token_invalid")
    try:
        return TokenPayload(
            sub=uuid.UUID(claims["sub"]),
            type=claims["type"],
            iat=datetime.fromtimestamp(claims["iat"], UTC),
            exp=datetime.fromtimestamp(claims["exp"], UTC),
            jti=uuid.UUID(claims["jti"]) if "jti" in claims else None,
            fam=uuid.UUID(claims["fam"]) if "fam" in claims else None,
        )
    except (ValueError, TypeError) as exc:
        raise TokenError("token_invalid") from exc


# --- Opaque one-time tokens (invitations, password resets, recovery codes) ------------------


def generate_url_token() -> str:
    return secrets.token_urlsafe(32)


def hash_token(token: str) -> str:
    """Tokens are high-entropy random values, so a fast hash is sufficient."""
    return hashlib.sha256(token.encode()).hexdigest()


def generate_csrf_token() -> str:
    return secrets.token_urlsafe(32)


def tokens_equal(a: str, b: str) -> bool:
    return hmac.compare_digest(a.encode(), b.encode())


def generate_recovery_codes(count: int = 10) -> list[str]:
    alphabet = "abcdefghjkmnpqrstuvwxyz23456789"  # no ambiguous characters
    codes = []
    for _ in range(count):
        raw = "".join(secrets.choice(alphabet) for _ in range(10))
        codes.append(f"{raw[:5]}-{raw[5:]}")
    return codes


def normalize_recovery_code(code: str) -> str:
    cleaned = "".join(ch for ch in code.lower() if ch.isalnum())
    return f"{cleaned[:5]}-{cleaned[5:]}"


# --- TOTP (RFC 6238) --------------------------------------------------------------------

TOTP_ISSUER = "Korinnia"


def generate_totp_secret() -> str:
    return pyotp.random_base32()


def totp_provisioning_uri(secret: str, email: str) -> str:
    return pyotp.TOTP(secret).provisioning_uri(name=email, issuer_name=TOTP_ISSUER)


def totp_qr_svg(uri: str) -> str:
    return str(segno.make(uri, error="m").svg_inline(scale=4, border=2))


def verify_totp(
    secret: str, code: str, *, last_counter: int | None, now: datetime | None = None
) -> int | None:
    """Return the matched time-step counter, or None. Accepts ±1 step of clock drift and
    rejects codes whose counter is not newer than `last_counter` (replay protection)."""
    code = code.strip().replace(" ", "")
    if not (code.isdigit() and len(code) == 6):
        return None
    totp = pyotp.TOTP(secret)
    at = now or utcnow()
    current = totp.timecode(at)
    for counter in (current - 1, current, current + 1):
        if last_counter is not None and counter <= last_counter:
            continue
        if hmac.compare_digest(totp.generate_otp(counter), code):
            return counter
    return None
