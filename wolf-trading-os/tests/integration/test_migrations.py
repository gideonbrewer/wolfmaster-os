"""Alembic migration integrity."""

from __future__ import annotations

import pytest
from sqlalchemy import create_engine, inspect

from tests.integration.conftest import _alembic

pytestmark = pytest.mark.integration


def test_upgrade_creates_expected_tables(scratch_database_url: str) -> None:
    engine = create_engine(scratch_database_url)
    try:
        inspector = inspect(engine)
        tables = set(inspector.get_table_names())
        assert {"trades", "import_batches", "alembic_version"} <= tables

        trade_columns = {c["name"] for c in inspector.get_columns("trades")}
        assert {
            "trade_id",
            "fingerprint",
            "source",
            "bot_name",
            "underlying_symbol",
            "quantity",
            "opened_at",
            "closed_at",
            "realized_pnl",
            "mfe_pct",
            "mae_pct",
            "raw_payload",
            "parse_sources",
            "tags",
        } <= trade_columns

        unique = inspector.get_unique_constraints("trades") + [
            i for i in inspector.get_indexes("trades") if i.get("unique")
        ]
        assert any("fingerprint" in (u.get("column_names") or []) for u in unique), (
            "fingerprint must be unique at the database level"
        )
    finally:
        engine.dispose()


def test_downgrade_and_reupgrade_cycle(scratch_database_url: str) -> None:
    _alembic(scratch_database_url, "base", down=True)
    engine = create_engine(scratch_database_url)
    try:
        assert "trades" not in inspect(engine).get_table_names()
    finally:
        engine.dispose()

    _alembic(scratch_database_url, "head")
    engine = create_engine(scratch_database_url)
    try:
        assert "trades" in inspect(engine).get_table_names()
    finally:
        engine.dispose()
