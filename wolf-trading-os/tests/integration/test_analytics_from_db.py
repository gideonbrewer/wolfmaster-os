"""Analytics over trades loaded from PostgreSQL — dashboard-path parity.

Guarantees acceptance criterion 7: dashboard metrics match the tested
calculation path, because the dashboard uses exactly `load_trades` +
`build_analytics_bundle` exercised here.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from sqlalchemy import create_engine

from wolf_trading_os.analytics import closed_trades, load_trades
from wolf_trading_os.ingestion.option_alpha import OptionAlphaImporter
from wolf_trading_os.services import build_analytics_bundle

FIXTURES = Path(__file__).parents[1] / "fixtures"

pytestmark = pytest.mark.integration


@pytest.fixture
def loaded_db(clean_database: str) -> str:
    OptionAlphaImporter(clean_database).import_files([FIXTURES / "option_alpha_sample.csv"])
    return clean_database


def test_bundle_from_database(loaded_db: str) -> None:
    engine = create_engine(loaded_db)
    try:
        df = load_trades(engine)
    finally:
        engine.dispose()

    assert len(df) == 12
    closed = closed_trades(df)
    assert len(closed) == 11  # one open BTC row has no realized pnl

    bundle = build_analytics_bundle(df)
    # Hand-checked sums over the fixture file:
    # 390 - 270 + 125 + 235 + 182 + 310 + 375 - 575 + 150 - 180 + 65 = 807
    assert bundle.core.total_pnl == pytest.approx(807.0)
    assert bundle.core.wins == 8
    assert bundle.core.losses == 3
    assert bundle.core.win_rate == pytest.approx(8 / 11)
    assert bundle.core.gross_profit == pytest.approx(1832.0)
    assert bundle.core.gross_loss == pytest.approx(1025.0)
    assert bundle.core.profit_factor == pytest.approx(1832.0 / 1025.0)
    assert bundle.equity.max_drawdown > 0
    assert bundle.excursion.trades_with_mfe == 11
    # Raw vs normalized must be distinct values
    assert bundle.normalized.per_contract_total_pnl != bundle.normalized.raw_total_pnl


def test_enriched_columns_present(loaded_db: str) -> None:
    engine = create_engine(loaded_db)
    try:
        df = load_trades(engine)
    finally:
        engine.dispose()
    for column in ("entry_hour", "exit_hour", "day_of_week", "month", "quantity_bucket"):
        assert column in df.columns
    spy_hulk = df[(df["strategy_family"] == "Hulk") & (df["underlying_symbol"] == "SPY")]
    assert not spy_hulk.empty
    assert set(spy_hulk["entry_hour"].dropna()) == {9}
