"""Spreadsheet-formula-injection protection on CSV exports (M2)."""

from __future__ import annotations

import pandas as pd

from wolf_trading_os.services.csv_export import safe_csv_bytes, sanitize_cell


class TestSanitizeCell:
    def test_formula_triggers_prefixed(self) -> None:
        assert sanitize_cell('=HYPERLINK("http://evil","x")') == '\'=HYPERLINK("http://evil","x")'
        assert sanitize_cell("+1+2") == "'+1+2"
        assert sanitize_cell("-2+3") == "'-2+3"
        assert sanitize_cell("@SUM(A1)") == "'@SUM(A1)"
        assert sanitize_cell("\t=1") == "'\t=1"
        assert sanitize_cell("\r=1") == "'\r=1"

    def test_normal_strings_untouched(self) -> None:
        assert sanitize_cell("Hulk 0DTE") == "Hulk 0DTE"
        assert sanitize_cell("SPY $595 Iron Butterfly") == "SPY $595 Iron Butterfly"

    def test_numbers_untouched(self) -> None:
        assert sanitize_cell(-575.0) == -575.0
        assert sanitize_cell(3) == 3
        assert sanitize_cell(None) is None

    def test_tag_lists_flattened(self) -> None:
        assert sanitize_cell(["=cmd", "safe"]) == "'=cmd, safe"


class TestSafeCsvBytes:
    def _df(self) -> pd.DataFrame:
        return pd.DataFrame(
            {
                "bot_name": ['=HYPERLINK("http://evil","click")', "Hulk [Live]"],
                "contract_description": ["+ACTIVE()", "SPY IB"],
                "strategy_name": ["@cmd", "Banshee"],
                "underlying_symbol": ["-SPY", "QQQ"],
                "tags": [["=t1", "ok"], []],
                "realized_pnl": [-575.0, 390.0],
            }
        )

    def test_dangerous_cells_neutralized(self) -> None:
        out = safe_csv_bytes(self._df()).decode("utf-8")
        lines = out.splitlines()
        assert "\"'=HYPERLINK" in lines[1]
        assert "'+ACTIVE()" in lines[1]
        assert "'@cmd" in lines[1]
        assert "'-SPY" in lines[1]
        assert "'=t1, ok" in lines[1]

    def test_negative_numbers_stay_numeric(self) -> None:
        out = safe_csv_bytes(self._df()).decode("utf-8")
        assert ",-575.0" in out.splitlines()[1]  # no apostrophe on numerics

    def test_source_dataframe_not_mutated(self) -> None:
        df = self._df()
        original = df["bot_name"].tolist()
        safe_csv_bytes(df)
        assert df["bot_name"].tolist() == original
