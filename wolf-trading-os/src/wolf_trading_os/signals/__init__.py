"""Signal ingestion — INTERFACE PLACEHOLDER ONLY (future phase).

Phase 1 contains no signal connectivity (no TradingView webhooks, no
Option Alpha API). This module defines the contract future signal sources
must satisfy. Per AGENTS.md: duplicate signals must never create
duplicate orders, so every signal carries a deterministic idempotency key.
"""

from __future__ import annotations

import datetime as dt
from typing import Protocol

from pydantic import BaseModel, ConfigDict


class Signal(BaseModel):
    """An external trading signal. A signal is a REQUEST for consideration;
    it never authorizes execution (AGENTS.md rule 2)."""

    model_config = ConfigDict(frozen=True)

    idempotency_key: str
    source: str
    symbol: str
    received_at: dt.datetime
    payload: dict[str, object]


class SignalSource(Protocol):
    """Contract for future signal providers (e.g. TradingView webhooks)."""

    def validate(self, raw: bytes) -> Signal:
        """Parse and validate a raw inbound message; must fail closed on
        missing, stale, malformed, or contradictory data."""
        ...
