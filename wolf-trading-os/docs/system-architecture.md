# System Architecture (Phase 1)

## Purpose

Phase 1 is the analytical foundation of a future multi-asset automated
trading platform. It ingests Option Alpha CSV trade exports, stores
canonical trades in PostgreSQL, computes performance analytics, and
serves a Streamlit dashboard. **It contains no order capability and no
broker connectivity** (AGENTS.md rule 13).

## Module map

```
src/wolf_trading_os/
├── config/       Environment-based settings (pydantic-settings, WTOS_* vars)
├── logging/      Structured JSON logging (structlog)
├── domain/       Canonical trade model (Pydantic v2) + shared enums
├── database/     SQLAlchemy 2 ORM, engine/session, repository helpers
├── ingestion/
│   └── option_alpha/
│       ├── schema.py       column names, aliases, required/optional sets
│       ├── values.py       tolerant scalar parsers (numbers, timestamps, tags)
│       ├── bot_parser.py   strategy attrs from bot names (never invents)
│       ├── fingerprint.py  deterministic SHA-256 trade fingerprint
│       ├── normalizer.py   raw row -> CanonicalTrade (+ errors/warnings)
│       └── importer.py     file/buffer import service + summary
├── analytics/    Pure functions over pandas DataFrames
│   ├── frames.py         DB -> DataFrame loading + shared enrichment
│   ├── core.py           win rate, profit factor, expectancy, streaks…
│   ├── normalization.py  per-contract / per-$1k / equal-weighted
│   ├── equity.py         equity curve, drawdown, durations
│   ├── excursion.py      MFE/MAE analysis
│   └── grouping.py       grouped breakdowns and comparisons
├── services/     AnalyticsBundle orchestration for UI/CLI
├── dashboard/    Streamlit app (overview, viz, explorer, import)
├── cli.py        import-option-alpha / run-dashboard / database-upgrade /
│                 database-reset-dev (dev-gated)
└── signals/, strategies/, risk/, execution/, brokers/
                  FUTURE-PHASE PLACEHOLDERS — interfaces/docstrings only
```

## Data flow

```
Option Alpha CSV ──> importer ──> normalizer ──> CanonicalTrade
      (file/upload)     │  fingerprint + batch-dedup + DB unique constraint
                        ▼
                  PostgreSQL (trades, import_batches)
                        │  analytics.frames.load_trades()
                        ▼
                pandas DataFrame ──> analytics functions ──> dashboard / CLI
```

Key invariants:

- The **database is the final duplicate gate** (unique `fingerprint`),
  not application memory.
- Analytics are **pure functions over DataFrames**, unit-testable
  without a database. The dashboard consumes the exact same functions
  the tests verify.
- The raw source row is preserved verbatim in `trades.raw_payload`
  (JSONB) so reprocessing/backfilling is always possible.
- Derived values carry provenance (`parse_sources`), and anything
  unparseable is NULL — never guessed (AGENTS.md rule 4).

## Boundaries reserved for future phases

| Package | Future role | Phase 1 content |
| --- | --- | --- |
| `signals/` | TradingView webhooks, other feeds | `Signal` model + `SignalSource` Protocol |
| `strategies/` | strategy runtime | `TradeRequest` model + `Strategy` Protocol |
| `risk/` | central risk engine with final authority | `RiskEngine` Protocol, verdict model |
| `execution/` | order lifecycle | **empty by design** — no interfaces |
| `brokers/` | IBKR / Coinbase adapters | read-only `BrokerStateReader` Protocol |

The deliberate asymmetry — read-side reconciliation contracts exist,
order-side contracts do not — implements AGENTS.md rules 8 and 13.

## Runtime topology (Docker Compose)

- `db`: PostgreSQL 16 with a named volume, healthchecked.
- `app`: Python 3.12 image; on start runs `database-upgrade` then serves
  Streamlit on :8501. Host `./data` is mounted read-only at `/data` for
  CSV imports via `docker compose exec`.

## Configuration

All configuration is environment-based (`WTOS_*`), loaded by
pydantic-settings, with `.env` support for local development. No
credentials in code or images. `database-reset-dev` refuses to run
unless `WTOS_ENVIRONMENT=development`.
