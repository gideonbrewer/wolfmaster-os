# Wolf Trading OS — Phase 1

Foundation for a production-grade, multi-asset automated trading platform.
**Phase 1 is analytics-only**: it imports Option Alpha CSV trade exports,
stores canonical trades in PostgreSQL, computes performance analytics, and
presents them in a Streamlit dashboard.

> ## ⚠️ Phase 1 cannot execute trades
>
> - There is **no code path capable of placing, routing, transmitting, or
>   simulating an order**.
> - **No broker or exchange integrations are implemented** — no IBKR, no
>   Coinbase, no TradingView, no Option Alpha API connectivity.
> - The `execution/`, `brokers/`, `risk/`, `signals/`, and `strategies/`
>   packages contain **interface definitions and placeholders only**.
> - A test (`tests/unit/test_no_execution_capability.py`) fails the build if
>   order-placement capability is introduced.
>
> See [AGENTS.md](AGENTS.md) for the permanent engineering rules.

## What Phase 1 does

- Imports one or more **Option Alpha CSV trade exports** (CLI, Python API, or
  dashboard upload).
- Validates and normalizes rows; malformed rows are reported without aborting
  the import.
- Prevents duplicate imports via a deterministic per-trade fingerprint backed
  by a database unique constraint.
- Stores canonical trades in **PostgreSQL** (SQLAlchemy 2 + Alembic).
- Computes performance analytics: win rate, profit factor, expectancy, equity
  curve, drawdown, MFE/MAE analysis, grouped breakdowns, and
  **quantity-normalized** metrics kept strictly separate from raw-dollar
  results.
- Serves a **Streamlit dashboard**: overview KPIs, visualizations, a filterable
  trade explorer with CSV export, and an import screen.

## Requirements

- Python 3.12+
- PostgreSQL 15+ (16 tested)
- Docker + Docker Compose (optional, for the containerized setup)

## Quick start (Docker)

```bash
cp .env.example .env          # adjust if desired; never commit .env
docker compose up --build
```

This starts PostgreSQL, runs Alembic migrations, and serves the dashboard at
<http://localhost:8501>.

Import a CSV inside the running container:

```bash
docker compose exec app wolf-trading-os import-option-alpha /data/your-export.csv
```

(Place CSV files in `./data/` on the host; it is mounted at `/data`.)

## Quick start (local)

```bash
python3.12 -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
cp .env.example .env          # point WTOS_DATABASE_URL at your Postgres

# create the database (adjust to your setup)
createdb wolf_trading_os_dev

# run migrations
wolf-trading-os database-upgrade

# import one or more Option Alpha CSV exports
wolf-trading-os import-option-alpha path/to/export.csv [more.csv ...]

# open the dashboard at http://localhost:8501
wolf-trading-os run-dashboard
```

## CLI

| Command | Purpose |
| --- | --- |
| `wolf-trading-os import-option-alpha FILE [FILE ...] [--date-order MDY|DMY]` | Import CSV exports; prints a JSON import summary |
| `wolf-trading-os run-dashboard` | Launch the Streamlit dashboard |
| `wolf-trading-os database-upgrade` | Run Alembic migrations to head |
| `wolf-trading-os database-reset-dev` | Drop + recreate schema — **blocked unless `WTOS_ENVIRONMENT=development` AND the target is a local dev/test-named database**; requires `--yes` (remote/shared targets additionally need `--force-unsafe-reset --confirm-database NAME`) |

## Running tests, linting, and type checks

```bash
# unit tests (no database needed)
pytest tests/unit

# integration tests (need a reachable PostgreSQL; uses WTOS_TEST_DATABASE_URL;
# creates/drops its own scratch database). With WTOS_REQUIRE_DB=1 (CI default)
# an unreachable database FAILS instead of skipping.
pytest tests/integration -m integration

# everything
pytest

# lint + format check
ruff check .
ruff format --check .

# type check
mypy
```

CI (GitHub Actions) runs the same commands against a PostgreSQL service
container on every push/PR — see `.github/workflows/ci.yml`.

## Importing Option Alpha CSV files

Export trade history from Option Alpha as CSV, then either:

1. **CLI**: `wolf-trading-os import-option-alpha export1.csv export2.csv`
2. **Dashboard**: open the *Import* page and upload files.
3. **Python**:

   ```python
   from wolf_trading_os.ingestion.option_alpha import OptionAlphaImporter
   summary = OptionAlphaImporter().import_files(["export.csv"])
   print(summary.model_dump())
   ```

Every import reports rows received / accepted / rejected / duplicates and
per-row validation warnings. Re-importing the same file (or overlapping
exports) never creates duplicate trades.

## Documentation

| Doc | Contents |
| --- | --- |
| [docs/system-architecture.md](docs/system-architecture.md) | Module boundaries, data flow, future phases |
| [docs/data-model.md](docs/data-model.md) | Canonical trade schema and fingerprinting |
| [docs/analytics-definitions.md](docs/analytics-definitions.md) | Exact formula for every metric |
| [docs/risk-policy.md](docs/risk-policy.md) | Risk-management principles (future phases) |
| [docs/execution-policy.md](docs/execution-policy.md) | Execution principles (future phases) |
| [docs/strategy-governance.md](docs/strategy-governance.md) | Champion/challenger promotion process |
| [docs/testing-policy.md](docs/testing-policy.md) | Test tiers and requirements |
| [docs/decisions.md](docs/decisions.md) | Architecture decision log |
| [docs/roadmap.md](docs/roadmap.md) | Phase 2+ outline |

## Known limitations (Phase 1)

- Only the Option Alpha CSV export format is supported as a data source.
- MFE/MAE analysis relies on Option Alpha's `highReturnPct` / `lowReturnPct`
  columns; intratrade excursion is not reconstructed from market data.
- Strategy attributes (delta, DTE, timeframe, live/paper) are parsed from bot
  names/descriptions on a best-effort basis; unparseable values are stored as
  `NULL`, never guessed.
- Percentage drawdown is only computed where mathematically valid (positive
  running peak); otherwise dollar drawdown is authoritative.
- Timestamps in Option Alpha exports carry no timezone; wall-clock values
  are stored verbatim and rows are marked explicitly timezone-unknown —
  UTC fields are populated only when a source carries an explicit offset.
- Returns/excursions are stored as decimal fractions (0.125 = 12.5%),
  matching Option Alpha's export convention; files that appear to use
  percentage points are rejected rather than silently converted.
- Slash dates are parsed month-first (the confirmed Option Alpha format)
  unless `--date-order DMY` is passed; contradictory in-file evidence
  rejects the file.
- No live data feeds, no broker reconciliation, no order capability of any
  kind (by design — see AGENTS.md rule 13).
