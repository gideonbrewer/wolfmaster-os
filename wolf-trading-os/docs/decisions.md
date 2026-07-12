# Architecture Decision Log

Format: newest last. Each entry: context → decision → consequences.

## ADR-001: Build in a `wolf-trading-os/` subdirectory of this repository

The host repository (`wolfmaster-os`) already contains an unrelated
static web app at its root. The trading platform lives entirely under
`wolf-trading-os/`, matching the requested project layout without
touching the existing app. The CI workflow lives at the repo root
(`.github/workflows/wolf-trading-os-ci.yml` — GitHub only reads
workflows there) with `paths`/`working-directory` scoping it to the
subproject.

## ADR-002: Two tables — `trades` + `import_batches`; DB is the dedup gate

Canonical trades and file-level import audits are separate concerns.
Duplicate prevention is enforced by a UNIQUE constraint on
`trades.fingerprint`, not only by application logic, so concurrent or
partial imports cannot create duplicates. Import batches record file
hash and row counts for a permanent audit trail.

## ADR-003: Fingerprint = SHA-256 over a frozen 12-field subset

Hashing the whole row would break dedup whenever Option Alpha adds or
removes an optional column. Hashing a frozen list of identity-bearing
fields (bot, type, description, symbol, quantity, open/close/expiration
dates, prices, premium, pnl) keeps fingerprints stable across re-exports.
A version prefix (`oa1`) makes future algorithm changes explicit.
Trade-off: a theoretical collision between two trades identical in all
12 fields; with minute-precision timestamps this is acceptable and
documented.

## ADR-004: Trade event times stored as naive timestamps

Option Alpha exports carry no timezone. Rather than guessing a zone (a
rule-4 violation), event times are stored as `timestamp without time
zone` exactly as exported and interpreted as exchange-local wall clock,
which is also what entry-hour/day-of-week analytics want. Audit columns
remain `timestamptz`.

## ADR-005: Decimal in the domain/DB, float64 in analytics

Monetary fields are `Decimal`/`NUMERIC` end-to-end for storage
(no float drift in the system of record). Analytics convert to float64
DataFrames — statistical aggregation does not need exact decimal
arithmetic and pandas/plotly are float-native.

## ADR-006: Analytics as pure functions over DataFrames

Every metric is a pure function `DataFrame -> dataclass/DataFrame`,
unit-testable without a database. The dashboard consumes exactly these
functions (via `services.build_analytics_bundle`), so tested formulas
and displayed numbers cannot diverge (acceptance criterion 7). An
integration test loads from PostgreSQL and re-verifies hand-computed
totals through the same path.

## ADR-007: Population rule — metrics use trades with non-null realized P&L

Open/unresolved trades are excluded from all performance metrics rather
than treated as zero-P&L (which would dilute win rate and expectancy).
The dashboard reports the excluded count explicitly.

## ADR-008: Profit factor is None (not ∞) when there are no losses

JSON-safe, chart-safe, and honest: "no losses yet" is a sample-size
statement, not an infinite edge.

## ADR-009: MFE capture ratio uses the aggregate form

`mean(return)/mean(mfe)` over trades with positive MFE, because
per-trade ratios explode as MFE→0 and their mean is dominated by
outliers (observed on fixture data: mean of per-trade ratios −0.29 vs
aggregate 0.56). The median per-trade ratio is kept as a robust
secondary statistic. Documented in analytics-definitions.md.

## ADR-010: Bot-name parsing is regex-based, provenance-tagged, fail-closed

Strategy attributes (family, delta, DTE, timeframe, sizing, live/paper,
version) are extracted only on explicit token matches; anything else is
NULL. Every populated field records its source in `parse_sources`
(bot_name / tags / derived). Contradictory live+paper markers resolve to
UNKNOWN. This implements "do not invent values" mechanically.

## ADR-011: Ingestion uses stdlib csv, not pandas

Row-level error reporting (reject row 4 with a reason, keep row 5) and
raw-string preservation are natural with `csv.reader`; pandas type
coercion would fight both. Pandas enters only at the analytics layer.

## ADR-012: `execution/` is empty even of interfaces

Other future packages (signals, strategies, risk, brokers) hold
Protocol contracts, but the execution package deliberately defines
nothing — an order-side interface would already be a step toward an
order path (AGENTS.md rule 13). Brokers expose only a read-side
reconciliation contract. A tripwire test enforces emptiness.

## ADR-013: `database-reset-dev` is double-gated

Requires both `WTOS_ENVIRONMENT=development` (checked at runtime,
refused otherwise with a distinct exit code) and an explicit `--yes`
flag. Fail closed on destructive operations.

## ADR-014: Dashboard is a single Streamlit app with sidebar sections

Overview / Visualizations / Trade explorer / Import as functions in one
app (not Streamlit multipage files) keeps navigation state simple and
lets all sections share one cached data loader (60s TTL, invalidated on
import). Charts use a CVD-validated palette; polarity (blue/red)
encodes P&L sign; raw vs normalized results are always shown as
separate charts, never dual axes.

## ADR-016: Fingerprint v2 (`oa2`) with occurrence indexing

Remediation of audit findings H1/M1. The oa1 fingerprint silently
dropped genuinely distinct trades whose 12 raw fields were identical
(same-minute identical fills), collided paper/live rows distinguishable
only by tags, and was sensitive to numeric formatting ("3" vs "3.0").

`oa2` hashes normalized identity fields (source, botName, tags, symbol,
description, expiration, openDate, closeDate, quantity, openPrice,
closePrice, pnl) plus a deterministic per-file occurrence index for
repeated identical rows: the k-th identical row in one file hashes with
`occ=k`, so both trades are preserved while re-imports of the same file
still deduplicate. Numeric fields are Decimal-canonicalized and
timestamps ISO-canonicalized before hashing, so equivalent formatting
deduplicates. Analytic/restatable fields (premium, risk, ror,
returnPct, MFE/MAE, type, status) are deliberately excluded — changes
to them are surfaced by the possible-correction detector rather than
minting a new identity.

Migration: `trades.fingerprint_version` records the algorithm ("oa1"
backfilled for pre-existing rows, "oa2" for new imports). Imports also
compute the legacy oa1 hash and deduplicate occurrence-1 rows against
stored oa1 rows, so pre-migration databases do not double-import on
re-import. Known limitations: (a) occurrence>1 rows re-imported into a
legacy database insert as new trades — correct, because oa1 had dropped
them; (b) occurrence indexing only distinguishes identical trades that
appear in the SAME export file; the same two identical trades split
across two different exports still collide (cross-file occurrence
counting would break re-import dedup). Both are documented in
data-model.md.

## ADR-017: Conflict-safe trade insertion

Remediation of audit finding H4. Trades are inserted with PostgreSQL
`INSERT ... ON CONFLICT (fingerprint) DO NOTHING RETURNING fingerprint`.
The unique constraint remains the final duplicate arbiter; an import
that loses a race to a concurrent import reports the row as a duplicate
instead of crashing with IntegrityError, and both imports persist their
audit batch records. A sanitized `SQLAlchemyError` handler remains as a
secondary layer: on unexpected database errors the file's transaction
rolls back atomically and the summary reports a clean error naming only
the exception class — never a stack trace or connection URL.

## ADR-015: Percent values stored in percent units as exported

`return_pct`, `ror`, `mfe_pct`, `mae_pct` keep Option Alpha's percent
units (12.5 = +12.5%). No silent conversion to fractions; the unit is
documented in the data model and analytics definitions.
