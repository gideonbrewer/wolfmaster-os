"""Rename return columns to *_fraction and widen scale (ADR-018).

Return/excursion values are canonically DECIMAL FRACTIONS
(0.125 == 12.5%). Pre-existing rows imported under the percent-unit
convention are converted in place (divide by 100) so stored data keeps
one consistent unit.

Revision ID: 7b41c2ad9c03
Revises: 6129e531bdd1
Create Date: 2026-07-12

"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "7b41c2ad9c03"
down_revision: str | None = "6129e531bdd1"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_RENAMES = [
    ("return_pct", "return_fraction"),
    ("mfe_pct", "mfe_fraction"),
    ("mae_pct", "mae_fraction"),
]


def upgrade() -> None:
    for old, new in _RENAMES:
        op.alter_column("trades", old, new_column_name=new)
    for column in ("return_fraction", "return_on_risk", "mfe_fraction", "mae_fraction"):
        op.alter_column(
            "trades",
            column,
            type_=sa.Numeric(14, 8),
            existing_type=sa.Numeric(12, 4),
        )
        # Pre-existing rows stored percent points; convert to fractions.
        op.execute(f"UPDATE trades SET {column} = {column} / 100 WHERE {column} IS NOT NULL")


def downgrade() -> None:
    for column in ("return_fraction", "return_on_risk", "mfe_fraction", "mae_fraction"):
        op.execute(f"UPDATE trades SET {column} = {column} * 100 WHERE {column} IS NOT NULL")
        op.alter_column(
            "trades",
            column,
            type_=sa.Numeric(12, 4),
            existing_type=sa.Numeric(14, 8),
        )
    for old, new in _RENAMES:
        op.alter_column("trades", new, new_column_name=old)
