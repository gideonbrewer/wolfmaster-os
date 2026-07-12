"""Best-effort parsing of strategy attributes from Option Alpha bot names.

Bot names are free-form, e.g.:

    "Hulk 0DTE 0.50Δ 3x SPY [Live]"
    "Hulk v2 - 1DTE 60 delta QQQ paper"
    "Iron Condor Weekly 2DTE x5"

Rules:
- Never invent values: a field is populated only when an explicit token
  matches; otherwise it stays None / UNKNOWN.
- Every populated field records its provenance in `parse_sources`.
"""

from __future__ import annotations

import re
from decimal import Decimal

from wolf_trading_os.domain import ParseSource, StrategyAttributes, TradeEnvironment

# 0.50Δ / .5Δ / 0.50 delta / 50Δ / 50 delta / 50d (trailing standalone "d")
_DELTA_DECIMAL = re.compile(r"(?<![\d.])(0?\.\d{1,3})\s*(?:Δ|∆|delta)\b", re.IGNORECASE)
_DELTA_INT = re.compile(r"(?<![\d.])(\d{1,2})\s*(?:Δ|∆|delta)\b", re.IGNORECASE)
_DTE = re.compile(r"(?<![\d.])(\d{1,3})\s*DTE\b", re.IGNORECASE)
# 3x / x3 / 3 contracts
_CONTRACTS = re.compile(
    r"(?:(?<![\w.])(\d{1,4})\s*x(?![\w])|(?<![\w])x\s*(\d{1,4})\b|(?<![\d.])(\d{1,4})\s+contracts?\b)",
    re.IGNORECASE,
)
_VERSION = re.compile(r"(?<![\w.])v(\d+(?:\.\d+)*)\b", re.IGNORECASE)
_LIVE = re.compile(r"(?<![\w])live(?![\w])", re.IGNORECASE)
_PAPER = re.compile(r"(?<![\w])paper(?![\w])", re.IGNORECASE)

_TIMEFRAME_TOKENS: dict[str, str] = {
    "intraday": "intraday",
    "scalp": "intraday",
    "0dte": "0DTE",
    "swing": "swing",
    "multiday": "multi-day",
    "multi-day": "multi-day",
    "daily": "daily",
    "weekly": "weekly",
    "monthly": "monthly",
}
_TIMEFRAME = re.compile(
    r"(?<![\w])(" + "|".join(re.escape(t) for t in _TIMEFRAME_TOKENS) + r")(?![\w])",
    re.IGNORECASE,
)

# Leading run of alphabetic words = strategy family candidate, stopping at
# config tokens (numbers, delta, env markers, punctuation).
_FAMILY = re.compile(r"^\s*([A-Za-z][A-Za-z']*(?:\s+[A-Za-z][A-Za-z']*)*)")
_FAMILY_STOPWORDS = {
    "live",
    "paper",
    "delta",
    "dte",
    "the",
    "bot",
    "v",
    "x",
    "intraday",
    "swing",
    "daily",
    "weekly",
    "monthly",
    "scalp",
    "multiday",
}


def parse_bot_name(bot_name: str | None) -> StrategyAttributes:
    """Extract strategy attributes from a bot name. Unmatched fields stay None."""
    if bot_name is None or not bot_name.strip():
        return StrategyAttributes()

    text = bot_name.strip()
    sources: dict[str, ParseSource] = {}

    target_delta = _parse_delta(text)
    if target_delta is not None:
        sources["target_delta"] = ParseSource.BOT_NAME

    dte_setting: int | None = None
    if m := _DTE.search(text):
        dte_setting = int(m.group(1))
        sources["dte_setting"] = ParseSource.BOT_NAME

    contract_count: int | None = None
    if m := _CONTRACTS.search(text):
        contract_count = int(next(g for g in m.groups() if g))
        sources["contract_count_setting"] = ParseSource.BOT_NAME

    version: str | None = None
    if m := _VERSION.search(text):
        version = f"v{m.group(1)}"
        sources["strategy_version"] = ParseSource.BOT_NAME

    timeframe: str | None = None
    if m := _TIMEFRAME.search(text):
        timeframe = _TIMEFRAME_TOKENS[m.group(1).lower()]
        sources["timeframe"] = ParseSource.BOT_NAME
    elif dte_setting == 0:
        # An explicit 0DTE setting is itself an intraday timeframe statement.
        timeframe = "0DTE"
        sources["timeframe"] = ParseSource.DERIVED

    environment = TradeEnvironment.UNKNOWN
    is_live = bool(_LIVE.search(text))
    is_paper = bool(_PAPER.search(text))
    if is_live != is_paper:  # contradictory markers -> stay UNKNOWN
        environment = TradeEnvironment.LIVE if is_live else TradeEnvironment.PAPER
        sources["environment"] = ParseSource.BOT_NAME

    family: str | None = None
    if m := _FAMILY.match(text):
        words = [w for w in m.group(1).split() if w.lower() not in _FAMILY_STOPWORDS]
        if words:
            family = " ".join(words)
            sources["strategy_family"] = ParseSource.BOT_NAME

    return StrategyAttributes(
        strategy_family=family,
        strategy_name=text,
        strategy_version=version,
        timeframe=timeframe,
        target_delta=target_delta,
        dte_setting=dte_setting,
        contract_count_setting=contract_count,
        environment=environment,
        parse_sources={**sources, "strategy_name": ParseSource.BOT_NAME}
        if sources or text
        else sources,
    )


def _parse_delta(text: str) -> Decimal | None:
    if m := _DELTA_DECIMAL.search(text):
        return Decimal(m.group(1)).normalize()
    if m := _DELTA_INT.search(text):
        value = int(m.group(1))
        if 1 <= value <= 99:
            # "50 delta" convention -> 0.50
            return (Decimal(value) / 100).normalize()
    return None
