# Roadmap

## Phase 1 — Analytics foundation (this phase) ✅

Option Alpha CSV ingestion, canonical PostgreSQL trade store,
performance analytics (raw vs quantity-normalized, equity/drawdown,
MFE/MAE, grouped comparisons), Streamlit dashboard, CLI, Docker Compose,
CI, documentation. **No order capability.**

## Phase 2 — Data breadth & signal intake (read-only)

- TradingView webhook receiver implementing the `SignalSource` contract
  (validate, idempotency-key, persist, log — no downstream action).
- Additional import sources (broker statements, exchange CSV exports)
  mapped into the same canonical trade model.
- Scheduled/incremental Option Alpha imports; import API hardening.
- Market-data snapshots sufficient to enrich analytics (e.g. true
  intratrade MFE/MAE reconstruction where data permits).
- Analytics: rolling-window metrics, per-strategy equity curves,
  benchmark comparison.

## Phase 3 — Strategy & risk engines (paper only)

- Strategy runtime implementing the `Strategy` contract; strategies emit
  `TradeRequest`s only.
- Central risk engine with layered limits, fail-closed evaluation, and
  full decision logging; kill switch.
- Champion/challenger scoreboard automation per
  strategy-governance.md (measurement, not promotion).
- Paper execution design review — interface contracts, order state
  machine, idempotency and reconciliation specs (docs before code).

## Phase 4 — Execution (paper first, live gated)

- Paper execution layer behind risk authorization; full event logging;
  reconciliation loops against broker state.
- IBKR adapter (paper), then Coinbase Advanced adapter (sandbox), each
  interface-first with contract tests.
- Live enablement only after: reconciliation soak, kill-switch drills,
  explicit per-environment configuration, and a recorded go decision
  (AGENTS.md rules 1, 3, 8, 12).

## Phase 5 — Portfolio & operations

- Portfolio-level risk aggregation across asset classes.
- Unified monitoring/alerting; SLOs for data freshness and
  reconciliation lag.
- Strategy allocation & capital management workflows.
