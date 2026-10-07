"""Operator commands: `python -m app.cli <command>`.

bootstrap                      create the first superadmin from SUPERADMIN_* env vars
create-superadmin EMAIL NAME   create a superadmin (password read from stdin / prompt)
reset-link EMAIL               print a one-time password-reset link for a user
disable-2fa EMAIL              turn off 2FA for a locked-out user
"""

from __future__ import annotations

import argparse
import asyncio
import getpass
import sys

from app.core.config import get_settings
from app.core.db import get_engine, get_sessionmaker
from app.core.errors import AppError
from app.core.logging import configure_logging
from app.services import users as user_service
from app.services.auth import get_user_by_email
from app.services.context import Actor

CLI_ACTOR = Actor(None, ip="cli")


def _read_password() -> str:
    if not sys.stdin.isatty():
        return sys.stdin.readline().rstrip("\n")
    first = getpass.getpass("Password: ")
    if first != getpass.getpass("Repeat password: "):
        raise SystemExit("passwords do not match")
    return first


async def run(args: argparse.Namespace) -> int:
    settings = get_settings()
    try:
        async with get_sessionmaker()() as session:
            if args.command == "bootstrap":
                user = await user_service.bootstrap_superadmin(session, settings)
                print(f"superadmin created: {user.email}" if user else "bootstrap: nothing to do")
                return 0

            if args.command == "create-superadmin":
                password = _read_password()
                if len(password) < settings.password_min_length:
                    raise SystemExit(
                        f"password must be at least {settings.password_min_length} characters"
                    )
                user = await user_service.create_user(
                    session,
                    email=args.email,
                    display_name=args.name,
                    password=password,
                    is_superadmin=True,
                    actor=CLI_ACTOR,
                )
                print(f"superadmin created: {user.email}")
                return 0

            user = await get_user_by_email(session, args.email)
            if user is None:
                print(f"no user with email {args.email}", file=sys.stderr)
                return 1
            if args.command == "reset-link":
                url, row = await user_service.create_password_reset(session, user, CLI_ACTOR)
                print(f"{url}\n(valid until {row.expires_at.isoformat()})")
            elif args.command == "disable-2fa":
                await user_service.admin_disable_2fa(session, user, CLI_ACTOR)
                print(f"2FA disabled for {user.email}")
            return 0
    except AppError as exc:
        print(f"error: {exc.code}", file=sys.stderr)
        return 1
    finally:
        await get_engine().dispose()


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="python -m app.cli",
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("bootstrap")
    p = sub.add_parser("create-superadmin")
    p.add_argument("email")
    p.add_argument("name")
    for name in ("reset-link", "disable-2fa"):
        sub.add_parser(name).add_argument("email")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    configure_logging(get_settings().log_level)
    return asyncio.run(run(args))


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
