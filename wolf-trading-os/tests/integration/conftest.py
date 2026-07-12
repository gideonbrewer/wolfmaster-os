"""Integration test infrastructure.

Creates a scratch PostgreSQL database, migrates it with Alembic, and
drops it afterwards. The server is taken from WTOS_TEST_DATABASE_URL
(falling back to a local default); tests are skipped if it is
unreachable — CI always provides one.
"""

from __future__ import annotations

import os
import uuid
from collections.abc import Iterator
from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, text
from sqlalchemy.engine import make_url

PROJECT_ROOT = Path(__file__).parents[2]

_SERVER_URL = os.environ.get(
    "WTOS_TEST_DATABASE_URL",
    "postgresql+psycopg://wolf:wolf@localhost:5432/postgres",
)


def _server_available() -> bool:
    try:
        engine = create_engine(_SERVER_URL, connect_args={"connect_timeout": 3})
        with engine.connect():
            return True
    except Exception:
        return False


pytestmark = pytest.mark.integration


@pytest.fixture(scope="session")
def scratch_database_url() -> Iterator[str]:
    """A freshly created, fully migrated scratch database (dropped on exit)."""
    if not _server_available():
        pytest.skip(f"PostgreSQL not reachable at {_SERVER_URL}")

    db_name = f"wtos_test_{uuid.uuid4().hex[:12]}"
    admin = create_engine(_SERVER_URL, isolation_level="AUTOCOMMIT")
    with admin.connect() as conn:
        conn.execute(text(f'CREATE DATABASE "{db_name}"'))

    # NB: str(URL) masks the password as "***"; render explicitly.
    url = make_url(_SERVER_URL).set(database=db_name).render_as_string(hide_password=False)
    try:
        _alembic(url, "head")
        yield url
    finally:
        with admin.connect() as conn:
            conn.execute(
                text(
                    "SELECT pg_terminate_backend(pid) FROM pg_stat_activity "
                    "WHERE datname = :db AND pid <> pg_backend_pid()"
                ),
                {"db": db_name},
            )
            conn.execute(text(f'DROP DATABASE IF EXISTS "{db_name}"'))
        admin.dispose()


def _alembic(db_url: str, revision: str, *, down: bool = False) -> None:
    config = Config(str(PROJECT_ROOT / "alembic.ini"))
    config.set_main_option("script_location", str(PROJECT_ROOT / "migrations"))
    config.attributes["configure_logger"] = False
    # env.py reads -x db_url=...
    config.cmd_opts = type("Opts", (), {"x": [f"db_url={db_url}"]})()
    if down:
        command.downgrade(config, revision)
    else:
        command.upgrade(config, revision)


@pytest.fixture
def clean_database(scratch_database_url: str) -> Iterator[str]:
    """Scratch database emptied of rows before each test."""
    engine = create_engine(scratch_database_url)
    with engine.begin() as conn:
        conn.execute(text("TRUNCATE trades, import_batches RESTART IDENTITY CASCADE"))
    engine.dispose()
    yield scratch_database_url
