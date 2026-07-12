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
| `return_pct`, `return_on_risk` | numeric(12,4), nullable | percent units (12.5 = +12.5%) |
| `mfe_pct`, `mae_pct` | numeric(12,4), nullable | from `highReturnPct` / `lowReturnPct` |
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

## Fingerprint (duplicate prevention)

`fingerprint = sha256("oa1" + 0x1F-joined values of the fixed field list)`

Field list (frozen; see `ingestion/option_alpha/fingerprint.py`):

```
botName, type, description, symbol, quantity, openDate, closeDate,
expiration, openPrice, closePrice, premium, pnl
```

Properties:

- Values are whitespace-trimmed; missing and empty are equivalent.
- Columns outside the list don't affect the fingerprint, so re-exports
  with added/removed optional columns still deduplicate.
- The `oa1` version prefix makes future algorithm changes explicit.
- Enforced by an application pre-check **and** a database UNIQUE
  constraint — concurrent imports cannot slip duplicates through.

Known limitation: two genuinely distinct trades identical in *all*
twelve fields would collide. With open/close timestamps at minute
precision this is not a realistic occurrence in Option Alpha exports.

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
