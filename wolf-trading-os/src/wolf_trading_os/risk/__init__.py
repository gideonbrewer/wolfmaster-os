"""Central risk management — INTERFACE PLACEHOLDER ONLY (future phase).

Phase 1 has no risk engine because there is nothing to authorize. The
contract below encodes the permanent rule (AGENTS.md rule 3): central
risk controls have FINAL authority over every future trade request, and
anything uncertain fails closed to rejection.
"""

from __future__ import annotations

import enum
from typing import Protocol

from pydantic import BaseModel, ConfigDict


class RiskDecision(enum.StrEnum):
    APPROVED = "approved"
    REJECTED = "rejected"


class RiskVerdict(BaseModel):
    model_config = ConfigDict(frozen=True)

    decision: RiskDecision
    reasons: tuple[str, ...]


class RiskEngine(Protocol):
    """Contract for the future central risk engine."""

    def review(self, request: object) -> RiskVerdict:
        """Review a TradeRequest. Missing, stale, malformed, or
        contradictory data must yield REJECTED (fail closed)."""
        ...
