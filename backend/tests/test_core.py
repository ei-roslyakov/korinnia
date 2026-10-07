from __future__ import annotations

import json
import logging
import sys

from pydantic import SecretStr

from app.core.config import Settings
from app.core.logging import JsonFormatter, configure_logging


def test_database_url_from_parts() -> None:
    s = Settings(
        postgres_host="db", postgres_user="u", postgres_password=SecretStr("p"), postgres_db="d"
    )
    assert s.database_url == "postgresql+psycopg://u:p@db:5432/d"
    assert s.libpq_conninfo == "postgresql://u:p@db:5432/d"


def test_database_url_encodes_credentials() -> None:
    s = Settings(
        postgres_host="db",
        postgres_user="app-db",
        postgres_password=SecretStr("p@ss#w/rd:%"),
        postgres_db="d",
    )
    assert s.database_url == "postgresql+psycopg://app-db:p%40ss%23w%2Frd%3A%25@db:5432/d"


def test_database_url_override() -> None:
    s = Settings(DATABASE_URL="postgresql+psycopg://x:y@h/z")
    assert s.database_url == "postgresql+psycopg://x:y@h/z"


def test_json_formatter_includes_extra() -> None:
    record = logging.LogRecord("t", logging.INFO, __file__, 1, "hello %s", ("world",), None)
    record.person_id = "123"
    out = json.loads(JsonFormatter().format(record))
    assert out["msg"] == "hello world"
    assert out["level"] == "info"
    assert out["person_id"] == "123"


def test_json_formatter_exception() -> None:
    try:
        raise ValueError("boom")
    except ValueError:
        record = logging.LogRecord("t", logging.ERROR, __file__, 1, "x", (), sys.exc_info())
    assert "ValueError: boom" in json.loads(JsonFormatter().format(record))["exc"]


def test_configure_logging_sets_level() -> None:
    configure_logging("warning")
    assert logging.getLogger().level == logging.WARNING
