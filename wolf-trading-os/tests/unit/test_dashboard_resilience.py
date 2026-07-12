"""Sanitized database-failure handling for the dashboard data path (item 15)."""

from __future__ import annotations

from sqlalchemy import create_engine

from wolf_trading_os.services import load_trades_safely

_BAD_URL = "postgresql+psycopg://wolf:supersecretpw@localhost:59999/nonexistent"


class TestLoadTradesSafely:
    def test_unreachable_database_returns_error_not_exception(self) -> None:
        engine = create_engine(_BAD_URL, connect_args={"connect_timeout": 2})
        try:
            df, error = load_trades_safely(engine)
        finally:
            engine.dispose()
        assert df is None
        assert error is not None
        assert "Database unavailable" in error

    def test_error_message_leaks_no_internals(self) -> None:
        engine = create_engine(_BAD_URL, connect_args={"connect_timeout": 2})
        try:
            _, error = load_trades_safely(engine)
        finally:
            engine.dispose()
        assert error is not None
        assert "supersecretpw" not in error  # no credentials
        assert "postgresql" not in error  # no connection URL
        assert "59999" not in error  # no host/port details
        assert "Traceback" not in error  # no stack trace
