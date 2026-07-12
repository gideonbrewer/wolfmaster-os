"""Tripwire: Phase 1 must contain no order-placement or simulation path.

AGENTS.md rule 13. Honest statement of guarantees (audit finding L1):

WHAT THIS DETECTS (accidental introduction of the obvious):
- order-placement function definitions/calls (place/submit/send/
  transmit/route/execute_order, placeOrder, create_order)
- imports of known broker/exchange client libraries
- broker SDK dependencies declared in pyproject.toml
- HTTP client usage or order-route URL strings inside the execution/
  and brokers/ packages
- any file other than the approved placeholder appearing in execution/

WHAT THIS CANNOT DETECT:
- arbitrarily named functions (def buy(...)), generic HTTP calls
  elsewhere in the codebase, obfuscated/getattr-composed calls,
  renamed broker library forks, or deliberately hidden functionality

This test is a tripwire against accidents, NOT proof that no
maliciously concealed order functionality exists. The real controls
are AGENTS.md rules, human code review, and dependency control —
see docs/testing-policy.md and docs/execution-policy.md.
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


def test_execution_package_contains_only_approved_files() -> None:
    """execution/ must hold exactly the approved placeholder module."""
    execution_dir = SRC_ROOT / "execution"
    files = sorted(
        p.name
        for p in execution_dir.iterdir()
        if p.is_file() and not p.name.endswith((".pyc", ".pyo"))
    )
    assert files == ["__init__.py"], f"unapproved files in execution/: {files}"


def test_no_http_clients_or_order_routes_in_execution_or_brokers() -> None:
    """No HTTP client usage or order-route strings in the reserved packages."""
    http_pattern = re.compile(
        r"^\s*(?:import|from)\s+(requests|httpx|aiohttp|urllib3|websocket|websockets)\b"
        r"|/v?\d*/orders?\b",
        re.MULTILINE | re.IGNORECASE,
    )
    offenders = []
    for package in ("execution", "brokers"):
        for path in sorted((SRC_ROOT / package).rglob("*.py")):
            if http_pattern.search(path.read_text(encoding="utf-8")):
                offenders.append(str(path.relative_to(SRC_ROOT)))
    assert not offenders, f"HTTP/order-route usage in reserved packages: {offenders}"


def test_no_broker_dependencies_declared() -> None:
    pyproject = SRC_ROOT.parents[1] / "pyproject.toml"
    if not pyproject.is_file():  # installed non-editable; source scan already ran
        return
    text = pyproject.read_text(encoding="utf-8").lower()
    for name in _FORBIDDEN_IMPORTS:
        assert f'"{name}' not in text, f"forbidden dependency declared: {name}"
