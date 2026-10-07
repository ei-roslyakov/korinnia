from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pyotp


def totp_code(secret: str, steps_ahead: int = 0) -> str:
    """A valid TOTP code. Use different `steps_ahead` (0 or 1) for consecutive uses within
    one test, since a code (time-step) can only be used once."""
    return pyotp.TOTP(secret).at(datetime.now(UTC) + timedelta(seconds=30 * steps_ahead))
