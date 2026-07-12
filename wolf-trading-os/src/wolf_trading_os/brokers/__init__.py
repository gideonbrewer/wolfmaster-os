"""Broker adapters — INTERFACE PLACEHOLDER ONLY (future phase).

Phase 1 has NO broker or exchange connectivity: no IBKR, no Coinbase, no
credentials, no network clients. Only a read-side reconciliation contract
is sketched, because AGENTS.md rule 8 requires broker state to be
reconciled against internal state in future phases. Order-side interfaces
are intentionally absent (AGENTS.md rule 13).
"""

from __future__ import annotations

from typing import Protocol


class BrokerStateReader(Protocol):
    """Future read-only contract: report broker-side state so it can be
    reconciled against internal records. Contains no order methods."""

    def snapshot_positions(self) -> dict[str, object]:
        """Return broker-side position state for reconciliation."""
        ...
