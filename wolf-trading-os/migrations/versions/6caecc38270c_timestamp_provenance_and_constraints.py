"""Timestamp provenance columns and database CHECK constraints (ADR-020).

Provenance: wall-clock event times stay in opened_at/closed_at; *_utc
are populated only when the source carried an explicit UTC offset;
source_timezone stays NULL (timezone-unknown) for pre-existing Option
Alpha rows — no timezone is guessed or backfilled.

Constraints are secondary defenses; application validation is primary.

Revision ID: 6caecc38270c
Revises: 7b41c2ad9c03
Create Date: 2026-07-12

"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "6caecc38270c"
down_revision: str | None = "7b41c2ad9c03"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_CHECKS: list[tuple[str, str]] = [
    ("ck_trades_quantity_positive", "quantity IS NULL OR quantity > 0"),
    ("ck_trades_fingerprint_not_empty", "fingerprint <> ''"),
    ("ck_trades_fingerprint_version_valid", "fingerprint_version IN ('oa1', 'oa2')"),
    ("ck_trades_source_valid", "source IN ('option_alpha', 'manual')"),
    (
        "ck_trades_timestamp_confidence_valid",
        "timestamp_confidence IN ('tz_unknown', 'explicit_offset')",
    ),
]


def upgrade() -> None:
    op.add_column("trades", sa.Column("opened_at_utc", sa.DateTime(timezone=True), nullable=True))
    op.add_column("trades", sa.Column("closed_at_utc", sa.DateTime(timezone=True), nullable=True))
    op.add_column("trades", sa.Column("source_timezone", sa.String(length=64), nullable=True))
    op.add_column("trades", sa.Column("exchange_timezone", sa.String(length=64), nullable=True))
    op.add_column(
        "trades",
        sa.Column(
            "timestamp_confidence",
            sa.String(length=32),
            server_default="tz_unknown",
            nullable=False,
        ),
    )
    # Venue knowledge for pre-existing option/equity rows (this is a fact
    # about the exchange, not a guess about the source clock, which stays
    # timezone-unknown: source_timezone remains NULL).
    op.execute(
        "UPDATE trades SET exchange_timezone = 'America/New_York' "
        "WHERE asset_class IN ('equity', 'equity_option')"
    )
    for name, condition in _CHECKS:
        op.create_check_constraint(name, "trades", condition)


def downgrade() -> None:
    for name, _ in reversed(_CHECKS):
        op.drop_constraint(name, "trades", type_="check")
    op.drop_column("trades", "timestamp_confidence")
    op.drop_column("trades", "exchange_timezone")
    op.drop_column("trades", "source_timezone")
    op.drop_column("trades", "closed_at_utc")
    op.drop_column("trades", "opened_at_utc")
