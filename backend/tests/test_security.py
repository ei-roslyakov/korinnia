from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta

import jwt
import pyotp
import pytest

from app.core import security
from app.core.security import (
    TokenError,
    create_token,
    decode_token,
    hash_password,
    normalize_recovery_code,
    verify_password,
    verify_totp,
)


def test_password_hash_roundtrip() -> None:
    h = hash_password("s3cret-password")
    assert h.startswith("$argon2id$")
    assert verify_password("s3cret-password", h)
    assert not verify_password("wrong", h)
    assert not verify_password("anything", None)
    assert not verify_password("x", "not-a-hash")
    assert not security.password_needs_rehash(h)


def test_jwt_roundtrip() -> None:
    uid, jti, fam = uuid.uuid4(), uuid.uuid4(), uuid.uuid4()
    token = create_token(uid, "refresh", timedelta(minutes=5), jti=jti, family_id=fam)
    payload = decode_token(token, "refresh")
    assert (payload.sub, payload.jti, payload.fam, payload.type) == (uid, jti, fam, "refresh")


def test_jwt_wrong_type_expired_and_tampered() -> None:
    uid = uuid.uuid4()
    access = create_token(uid, "access", timedelta(minutes=5))
    with pytest.raises(TokenError, match="token_invalid"):
        decode_token(access, "refresh")
    old = create_token(
        uid, "access", timedelta(minutes=5), now=datetime.now(UTC) - timedelta(hours=1)
    )
    with pytest.raises(TokenError, match="token_expired"):
        decode_token(old, "access")
    forged = jwt.encode(
        {"sub": str(uid), "type": "access", "iat": 0, "exp": 2**31},
        "another-signing-key-of-32-bytes!!",
    )
    with pytest.raises(TokenError, match="token_invalid"):
        decode_token(forged, "access")
    bad_sub = jwt.encode(
        {"sub": "not-a-uuid", "type": "access", "iat": 0, "exp": 2**31},
        security._secret(),
        algorithm="HS256",
    )
    with pytest.raises(TokenError, match="token_invalid"):
        decode_token(bad_sub, "access")


def test_recovery_codes() -> None:
    codes = security.generate_recovery_codes()
    assert len(set(codes)) == 10
    assert all(len(c) == 11 and c[5] == "-" for c in codes)
    assert normalize_recovery_code(codes[0].upper().replace("-", " ")) == codes[0]


def test_totp_window_and_replay() -> None:
    secret = security.generate_totp_secret()
    now = datetime.now(UTC)
    totp = pyotp.TOTP(secret)
    counter = verify_totp(secret, totp.at(now), last_counter=None, now=now)
    assert counter == totp.timecode(now)
    # Replay of the same step is rejected; previous step (clock drift) also blocked after use.
    assert verify_totp(secret, totp.at(now), last_counter=counter, now=now) is None
    # Next step is still accepted (drift tolerance), far future is not.
    assert verify_totp(secret, totp.at(now + timedelta(seconds=30)), last_counter=counter, now=now)
    assert (
        verify_totp(secret, totp.at(now + timedelta(minutes=5)), last_counter=None, now=now) is None
    )
    assert verify_totp(secret, "abc", last_counter=None) is None
    assert verify_totp(secret, "12345", last_counter=None) is None


def test_totp_qr_svg() -> None:
    uri = security.totp_provisioning_uri(security.generate_totp_secret(), "a@b.c")
    assert uri.startswith("otpauth://totp/Korinnia:")
    assert security.totp_qr_svg(uri).startswith("<svg")
