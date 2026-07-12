"""Strategy definitions — INTERFACE PLACEHOLDER ONLY (future phase).

Phase 1 has no strategy runtime. Per AGENTS.md: a strategy may REQUEST a
trade but may never authorize execution, and new strategy versions may
not promote themselves into production (see docs/strategy-governance.md).
"""

from __future__ import annotations

from typing import Protocol

from pydantic import BaseModel, ConfigDict


class TradeRequest(BaseModel):
    """A strategy's request for a trade. It is NOT an order: central risk
    controls (wolf_trading_os.risk) hold final authority."""

    model_config = ConfigDict(frozen=True)

    idempotency_key: str
    strategy_name: str
    strategy_version: str
    symbol: str
    rationale: str
    parameters: dict[str, object]


class Strategy(Protocol):
    """Contract for future strategy implementations."""

    name: str
    version: str

    def evaluate(self, context: dict[str, object]) -> TradeRequest | None:
        """Return a trade REQUEST, or None. Capital-related uncertainty
        must result in no action (AGENTS.md rule 14)."""
        ...
