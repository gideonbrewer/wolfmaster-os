"""Best-effort parsing of strategy attributes from Option Alpha bot names.

Bot names are free-form, e.g.:

    "Hulk 0DTE 0.50Δ 3x SPY [Live]"
    "Hulk v2 - 1DTE 60 delta QQQ (paper)"
    "Iron Condor Weekly 2DTE x5 - Live"

Rules (audit remediation H2/M8):
- Never invent values: a field is populated only when an explicit token
  matches; otherwise it stays None / UNKNOWN.
- Environment is CONSERVATIVE: only delimited markers count — "[Live]",
  "(paper)", "- Live", "Live:" or an exact live/paper tag. A brand word
  ("Live Wire Momentum", "Paper Tiger") is never an environment marker.
- Conflicts fail closed: when distinct values match one attribute, the
  attribute stays None/UNKNOWN and a parse warning is emitted. The first
  match is never silently chosen.
- Every populated field records its provenance in `parse_sources`.
"""

from __future__ import annotations

import re
from decimal import Decimal

from wolf_trading_os.domain import ParseSource, StrategyAttributes, TradeEnvironment

# 0.50Δ / .5Δ / 0.50 delta / 50Δ / 50 delta / .6 D (real-export notation).
# The bare "D" suffix is accepted only for decimal-form values: integer
# forms like "50 D" stay unparsed ("D" could mean days).
_DELTA_DECIMAL = re.compile(r"(?<![\d.])(0?\.\d{1,3})\s*(?:Δ|∆|delta\b|D(?![\w]))", re.IGNORECASE)
_DELTA_INT = re.compile(r"(?<![\d.])(\d{1,2})\s*(?:Δ|∆|delta)\b", re.IGNORECASE)
_DTE = re.compile(r"(?<![\d.])(\d{1,3})\s*DTE\b", re.IGNORECASE)
# 3x / x3 / 3 contracts
_CONTRACTS = re.compile(
    r"(?:(?<![\w.])(\d{1,4})\s*x(?![\w])|(?<![\w])x\s*(\d{1,4})\b|(?<![\d.])(\d{1,4})\s+contracts?\b)",
    re.IGNORECASE,
)
_VERSION = re.compile(r"(?<![\w.])v(\d+(?:\.\d+)*)\b", re.IGNORECASE)

# Environment: DELIMITED markers only (H2). Bare words never match.
_ENV_MARKERS = re.compile(
    r"""
    \[\s*(?P<bracket>live|paper)\s*\]        # [Live]
    | \(\s*(?P<paren>live|paper)\s*\)       # (Live)
    | (?:^|\s)[-–—]\s*(?P<dash>live|paper)\b # - Live (hyphen/en/em dash)
    | (?:^|\s)(?P<colon>live|paper)\s*:      # Live:
    | _(?P<uscore>live|paper)(?=$|[\s:(])    # Hulk_OG_Live: (trailing _Live token)
    """,
    re.IGNORECASE | re.VERBOSE,
)

_TIMEFRAME_TOKENS: dict[str, str] = {
    "intraday": "intraday",
    "scalp": "intraday",
    "scalper": "intraday",
    "scalping": "intraday",
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
# Real-export "N TF" tokens ("10 TF") are captured verbatim as "NTF".
# Semantics (presumed minutes) are unconfirmed — the token is recorded,
# never interpreted.
_TIMEFRAME_TF = re.compile(r"(?<![\d.])(\d{1,3})\s*TF\b", re.IGNORECASE)

# Leading run of alphabetic words = strategy family candidate, stopping at
# config tokens. "live"/"paper" are NOT stopwords: brand words stay part
# of the family name ("Live Wire Momentum").
_FAMILY = re.compile(r"^\s*([A-Za-z][A-Za-z']*(?:\s+[A-Za-z][A-Za-z']*)*)")
_FAMILY_STOPWORDS = {
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


def _distinct(values: list[str]) -> list[str]:
    seen: dict[str, None] = {}
    for v in values:
        seen.setdefault(v, None)
    return list(seen)


def parse_bot_name(bot_name: str | None) -> StrategyAttributes:
    """Extract strategy attributes from a bot name. Unmatched fields stay
    None; conflicting matches stay None/UNKNOWN with a warning."""
    if bot_name is None or not bot_name.strip():
        return StrategyAttributes()

    text = bot_name.strip()
    sources: dict[str, ParseSource] = {}
    warnings: list[str] = []

    def resolve(field: str, matches: list[str]) -> str | None:
        """Single distinct match wins; conflicts fail closed with a warning."""
        distinct = _distinct(matches)
        if not distinct:
            return None
        if len(distinct) > 1:
            warnings.append(
                f"bot name has conflicting {field} values {distinct}; stored as unknown"
            )
            return None
        sources[field] = ParseSource.BOT_NAME
        return distinct[0]

    # --- delta -----------------------------------------------------------
    delta_matches = [str(Decimal(m).normalize()) for m in _DELTA_DECIMAL.findall(text)]
    delta_matches += [
        str((Decimal(m) / 100).normalize()) for m in _DELTA_INT.findall(text) if 1 <= int(m) <= 99
    ]
    delta_text = resolve("target_delta", delta_matches)
    target_delta = Decimal(delta_text) if delta_text is not None else None

    # --- DTE setting -------------------------------------------------------
    dte_text = resolve("dte_setting", [str(int(m)) for m in _DTE.findall(text)])
    dte_setting = int(dte_text) if dte_text is not None else None

    # --- contract count ----------------------------------------------------
    contract_matches = [
        str(int(next(g for g in groups if g))) for groups in _CONTRACTS.findall(text)
    ]
    contracts_text = resolve("contract_count_setting", contract_matches)
    contract_count = int(contracts_text) if contracts_text is not None else None

    # --- version -----------------------------------------------------------
    version_text = resolve("strategy_version", [f"v{m}" for m in _VERSION.findall(text)])

    # --- timeframe -----------------------------------------------------------
    timeframe_matches = [_TIMEFRAME_TOKENS[m.lower()] for m in _TIMEFRAME.findall(text)]
    timeframe_matches += [f"{int(m)}TF" for m in _TIMEFRAME_TF.findall(text)]
    # "0DTE" is a strict specialization of "intraday", not a conflict
    # ("Scalper 0DTE ..."): keep the more specific token.
    if set(_distinct(timeframe_matches)) == {"intraday", "0DTE"}:
        timeframe_matches = ["0DTE"]
    timeframe = resolve("timeframe", timeframe_matches)
    if timeframe is None and not any("timeframe" in w for w in warnings) and dte_setting == 0:
        # An explicit 0-DTE setting is itself an intraday timeframe statement.
        timeframe = "0DTE"
        sources["timeframe"] = ParseSource.DERIVED

    # --- environment: delimited markers only --------------------------------
    env_matches = [next(g for g in m.groups() if g).lower() for m in _ENV_MARKERS.finditer(text)]
    environment = TradeEnvironment.UNKNOWN
    distinct_envs = _distinct(env_matches)
    if len(distinct_envs) == 1:
        environment = (
            TradeEnvironment.LIVE if distinct_envs[0] == "live" else TradeEnvironment.PAPER
        )
        sources["environment"] = ParseSource.BOT_NAME
    elif len(distinct_envs) > 1:
        warnings.append(
            "bot name has conflicting live/paper markers; environment stored as unknown"
        )

    # --- family: leading words, with delimited env markers removed ----------
    family: str | None = None
    family_text = _ENV_MARKERS.sub(" ", text).strip()
    if m := _FAMILY.match(family_text):
        words = [w for w in m.group(1).split() if w.lower() not in _FAMILY_STOPWORDS]
        if words:
            family = " ".join(words)
            sources["strategy_family"] = ParseSource.BOT_NAME

    return StrategyAttributes(
        strategy_family=family,
        strategy_name=text,
        strategy_version=version_text,
        timeframe=timeframe,
        target_delta=target_delta,
        dte_setting=dte_setting,
        contract_count_setting=contract_count,
        environment=environment,
        parse_sources={**sources, "strategy_name": ParseSource.BOT_NAME},
        warnings=tuple(warnings),
    )
