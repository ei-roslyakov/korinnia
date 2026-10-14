"""Low-level security primitives: password hashing, JWTs, one-time tokens, TOTP."""

from __future__ import annotations

import base64
import hashlib
import hmac
import secrets
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from functools import lru_cache
from typing import Any, Literal

import jwt
import pyotp
import segno
from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerificationError, VerifyMismatchError
from cryptography.fernet import Fernet, InvalidToken, MultiFernet
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.hkdf import HKDF

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
    # End of the sign-in session (access tokens).
    sx: datetime | None = None


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
    session_expires_at: datetime | None = None,
) -> str:
    """`session_expires_at` caps the token's lifetime and is carried as the `sx` claim."""
    issued = (now or utcnow()).replace(microsecond=0)
    expires = issued + ttl
    if session_expires_at is not None:
        expires = min(expires, session_expires_at)
    claims: dict[str, Any] = {
        "sub": str(user_id),
        "type": token_type,
        "iat": int(issued.timestamp()),
        "exp": int(expires.timestamp()),
    }
    if session_expires_at is not None:
        claims["sx"] = int(session_expires_at.timestamp())
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
            sx=datetime.fromtimestamp(claims["sx"], UTC) if "sx" in claims else None,
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


# --- Encryption at rest -----------------------------------------------------------------

# Stored values carry a version prefix; a value without it is legacy plaintext.
ENCRYPTED_PREFIX = "enc1:"


class DecryptionError(Exception):
    """A stored secret cannot be decrypted with the configured keys."""


def _derived_key(secret: str) -> bytes:
    raw = HKDF(
        algorithm=hashes.SHA256(), length=32, salt=None, info=b"korinnia/data-encryption"
    ).derive(secret.encode())
    return base64.urlsafe_b64encode(raw)


@lru_cache(maxsize=4)
def _fernet(data_key: str | None, secret_key: str) -> MultiFernet:
    # DATA_ENCRYPTION_KEY (when set) encrypts; the key derived from SECRET_KEY still decrypts,
    # so setting DATA_ENCRYPTION_KEY later keeps existing secrets readable.
    keys = [_derived_key(data_key)] if data_key else []
    keys.append(_derived_key(secret_key))
    return MultiFernet([Fernet(k) for k in keys])


def _current_fernet() -> MultiFernet:
    settings = get_settings()
    data_key = settings.data_encryption_key
    # An empty value (unset in docker compose) means "not set".
    return _fernet(
        (data_key.get_secret_value() if data_key else "") or None,
        settings.secret_key.get_secret_value(),
    )


def encrypt_secret(plain: str) -> str:
    token = _current_fernet().encrypt(plain.encode()).decode()
    return ENCRYPTED_PREFIX + token


def decrypt_secret(stored: str) -> str:
    if not stored.startswith(ENCRYPTED_PREFIX):
        return stored
    try:
        return _current_fernet().decrypt(stored[len(ENCRYPTED_PREFIX) :].encode()).decode()
    except InvalidToken as exc:
        raise DecryptionError(
            "stored secret cannot be decrypted: SECRET_KEY or DATA_ENCRYPTION_KEY changed"
        ) from exc
