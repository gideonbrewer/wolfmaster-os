# Data Model

## Tables

### `trades` — canonical trades

One row per imported trade, normalized across (future) sources. The
model is designed to carry stocks, equity options, crypto, and futures
without schema change.

| Column | Type | Notes |
| --- | --- | --- |
| `trade_id` | UUID PK | internal identity |
| `fingerprint` | varchar(64), **UNIQUE**, indexed | deterministic dedup key (below) |
| `fingerprint_version` | varchar(8), not null | fingerprint algorithm: `oa1` (legacy, pre-migration rows) or `oa2` |
| `source` | varchar | `option_alpha` (Phase 1) |
| `import_batch_id` | FK → import_batches | audit linkage (SET NULL on batch delete) |
| `strategy_family` | varchar, nullable | parsed from bot name (e.g. "Hulk") |
| `strategy_name` | varchar, nullable | cleaned bot name |
| `strategy_version` | varchar, nullable | parsed `vN(.N)` token |
| `bot_name` | varchar, indexed | as exported |
| `environment` | varchar | `live` / `paper` / `unknown` |
| `asset_class` | varchar | `equity` / `equity_option` / `crypto` / `future` / `unknown` |
| `instrument_type` | varchar | `iron_condor`, `vertical_spread`, `single_option`, … |
| `underlying_symbol` | varchar, indexed | uppercased |
| `contract_description` | text, nullable | as exported |
| `direction` | varchar | `long`/`short`/`credit`/`debit`/`neutral`/`unknown` |
| `status` | varchar | `open`/`closed`/`expired`/`canceled`/`unknown` |
| `quantity` | numeric(20,8), nullable | contracts/shares/units; must be > 0 |
| `opened_at`, `closed_at`, `expires_at` | timestamp (no tz) | exchange-local wall clock, as exported |
| `dte_at_entry` | int, nullable | derived: `expiration.date - openDate.date` |
| `days_in_trade` | numeric, nullable | from export |
| `entry_price`, `exit_price` | numeric(20,8), nullable | per-unit prices |
| `premium` | numeric(20,4), nullable | premium / capital deployed |
| `risk` | numeric(20,4), nullable | max defined risk |
| `realized_pnl` | numeric(20,4), nullable | NULL ⇒ open/unresolved; excluded from performance metrics |
| `return_fraction`, `return_on_risk` | numeric(14,8), nullable | DECIMAL FRACTIONS (0.125 = +12.5%), ADR-018 |
| `mfe_fraction`, `mae_fraction` | numeric(14,8), nullable | from `highReturnPct` / `lowReturnPct`, decimal fractions |
| `mfe_at`, `mae_at` | timestamp (no tz), nullable | excursion timestamps |
| `underlying_entry_price`, `underlying_exit_price` | numeric, nullable | from `underlyingOpen/Close` |
| `timeframe` | varchar, nullable | parsed token (`0DTE`, `swing`, …) |
| `target_delta` | numeric(6,4), nullable | parsed (0.50 = 50Δ) |
| `dte_setting` | int, nullable | parsed configured DTE |
| `contract_count_setting` | int, nullable | parsed sizing setting |
| `parse_sources` | JSONB | field → provenance (`source_column`/`bot_name`/`tags`/`derived`) |
| `tags` | varchar[] | split on `,;|` |
| `raw_payload` | JSONB | original row, verbatim (non-empty cells) |
| `created_at`, `updated_at` | timestamptz | audit |

Additional indexes: `(bot_name, opened_at)`, `strategy_family`, `opened_at`.

### `import_batches` — import audit trail

One row per import attempt of one file: `source`, `filename`,
`file_sha256`, `rows_received/accepted/rejected/duplicate`, `warnings`
(JSONB), `created_at`.

## Fingerprint (duplicate prevention) — v2 (`oa2`)

`fingerprint = sha256("oa2" + 0x1F-joined normalized identity values + "occ=k")`

Identity fields (frozen; see `ingestion/option_alpha/fingerprint.py`):

```
source, botName, tags, symbol, description,
expiration, openDate, closeDate,          (ISO-canonicalized)
quantity, openPrice, closePrice, pnl      (Decimal-canonicalized)
```

Deliberately excluded (restatable analytics — changes are surfaced by
the possible-correction detector instead): type, status, premium, risk,
ror, returnPct, ev, alpha, highReturnPct/lowReturnPct (+dates),
daysInTrade, underlyingOpen/underlyingClose.

Properties:

- Numeric fields hash equally across formatting ("3" == "3.0" == "$3");
  timestamps hash equally across formats; strings are trimmed; missing
  and empty are equivalent.
- `occ=k` is the 1-based occurrence index of the row among identical
  rows in the SAME file, so repeated identical source rows are
  preserved as distinct trades while re-imports still deduplicate
  (ADR-016). The importer warns whenever occurrences > 1 are detected.
- Enforced by `INSERT .. ON CONFLICT DO NOTHING` against the UNIQUE
  constraint — concurrent imports cannot slip duplicates through or
  crash (ADR-017).
- `fingerprint_version` records the algorithm per row. Legacy `oa1`
  rows (pre-migration) still deduplicate: imports compute the oa1 hash
  as well and skip occurrence-1 rows already stored as oa1.

Known limitations (documented, accepted): (a) two identical trades
split across two *different* export files still collide — occurrence
indexing is per-file by design, because cross-file counting would break
re-import dedup; (b) a corrected re-export (e.g. restated pnl) mints a
new fingerprint — the possible-correction detector flags these instead
of silently merging or duplicating.

## Timezone policy

Option Alpha exports carry no timezone. Trade event times are stored in
`timestamp without time zone` exactly as exported and interpreted as
exchange-local (US/Eastern) wall-clock. Entry-hour/day-of-week analytics
therefore reflect exchange session time. Audit columns
(`created_at`/`updated_at`) are `timestamptz`.

## Null policy

A NULL means "the source did not confidently provide this" — never a
default. Performance metrics operate only on rows where the relevant
inputs are non-null (documented per metric in analytics-definitions.md).

## Return-unit convention

Returns/excursions are decimal fractions end to end (0.125 = +12.5%).
`%`-suffixed cells are divided by 100 at parse time. Files whose
`ror` values are ~100x `pnl/risk` are rejected as percent-point exports
(no silent conversion); individually inconsistent rows produce import
warnings. See ADR-018.

## Date-order convention

Slash dates parse under the file-level `--date-order` option (default
MDY, the confirmed Option Alpha convention). Any cell valid only under
the opposite order rejects the whole file (ADR-019). ISO-8601 is always
accepted, including explicit UTC offsets.
