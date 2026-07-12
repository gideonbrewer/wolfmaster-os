"""Guard test: Phase 1 must contain no order-placement or simulation path.

AGENTS.md rule 13. This test scans the installed package source for
symbols and dependencies that would indicate an order path. It is a
tripwire, not a proof — but it fails loudly if someone adds the obvious
things.
"""

from __future__ import annotations

import re
from pathlib import Path

import wolf_trading_os

SRC_ROOT = Path(wolf_trading_os.__file__).parent

# Function/method definitions or calls that would indicate an order path.
_FORBIDDEN_PATTERNS = [
    r"\bdef\s+(place|submit|send|transmit|route|execute)_order\b",
    r"\bdef\s+(place|submit|transmit)_trade\b",
    r"\bcreate_order\s*\(",
    r"\bplaceOrder\b",  # IBKR API
]

_FORBIDDEN_IMPORTS = [
    "ib_insync",
    "ibapi",
    "ccxt",
    "coinbase",
    "alpaca",
]


def _python_sources() -> list[Path]:
    files = sorted(SRC_ROOT.rglob("*.py"))
    assert files, "no sources found — packaging changed?"
    return files


def test_no_order_placement_symbols() -> None:
    offenders: list[str] = []
    for path in _python_sources():
        text = path.read_text(encoding="utf-8")
        for pattern in _FORBIDDEN_PATTERNS:
            if re.search(pattern, text, re.IGNORECASE):
                offenders.append(f"{path.relative_to(SRC_ROOT)}: {pattern}")
    assert not offenders, f"order-capable code found in Phase 1: {offenders}"


def test_no_broker_client_imports() -> None:
    import_re = re.compile(
        r"^\s*(?:import|from)\s+(" + "|".join(_FORBIDDEN_IMPORTS) + r")\b", re.MULTILINE
    )
    offenders = [
        str(path.relative_to(SRC_ROOT))
        for path in _python_sources()
        if import_re.search(path.read_text(encoding="utf-8"))
    ]
    assert not offenders, f"broker/exchange client imported in Phase 1: {offenders}"


def test_execution_package_defines_nothing_executable() -> None:
    """The execution package must stay an empty documentation stub."""
    from wolf_trading_os import execution

    public = [n for n in vars(execution) if not n.startswith("_")]
    assert public == [], f"execution package must define nothing, found: {public}"


def test_no_broker_dependencies_declared() -> None:
    pyproject = SRC_ROOT.parents[1] / "pyproject.toml"
    if not pyproject.is_file():  # installed non-editable; source scan already ran
        return
    text = pyproject.read_text(encoding="utf-8").lower()
    for name in _FORBIDDEN_IMPORTS:
        assert f'"{name}' not in text, f"forbidden dependency declared: {name}"
