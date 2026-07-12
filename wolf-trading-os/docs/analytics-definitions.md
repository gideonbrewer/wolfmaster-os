# Analytics Definitions

Every metric below is implemented as a pure function over a pandas
DataFrame and verified by unit tests (`tests/unit/test_analytics_*.py`).
Changing a formula requires changing this document and the tests in the
same commit.

**Population**: unless stated otherwise, all metrics operate on trades
with a non-null `realized_pnl` ("closed trades"). Open/unresolved trades
never contaminate performance numbers.

**Units**: dollar metrics are raw dollars. Returns and excursions
(`return_fraction`, `return_on_risk`, `mfe_fraction`, `mae_fraction`)
are DECIMAL FRACTIONS: 0.125 means +12.5%, exactly as exported by
Option Alpha (ADR-018). Values are multiplied by 100 only at display
time. The importer rejects whole files that appear to use percent-point
units instead (ror vs pnl/risk consistency check).

## Core metrics (`analytics/core.py`)

| Metric | Formula |
| --- | --- |
| Trade count | `N = count(pnl not null)` |
| Total P&L | `Σ pnl` |
| Average / median P&L | `mean(pnl)`, `median(pnl)` |
| Wins / losses / flats | `count(pnl > 0)`, `count(pnl < 0)`, `count(pnl == 0)` |
| Win rate | `wins / N` (flats count against the win rate) |
| Average winner | `mean(pnl | pnl > 0)`; None if no winners |
| Average loser | `mean(pnl | pnl < 0)` (negative); None if no losers |
| Payoff ratio | `avg_winner / |avg_loser|` |
| Gross profit | `Σ (pnl | pnl > 0)` |
| Gross loss | `|Σ (pnl | pnl < 0)|` (positive magnitude) |
| Profit factor | `gross_profit / gross_loss`; **None when gross_loss = 0** (not ∞) |
| Expectancy per trade | `mean(pnl)` ≡ `win_rate·avg_winner + loss_rate·avg_loser` (identity tested) |
| Average / median return | `mean(return_fraction)`, `median(return_fraction)` over non-null returns |
| Best / worst trade | `max(pnl)`, `min(pnl)` |
| Max consecutive wins/losses | longest run of `pnl > 0` (resp. `< 0`) in **close-time order** (fallback: open time); flats break both streaks |

## Position-size normalization (`analytics/normalization.py`)

Raw dollars are size-dependent; the following are size-independent and
must never be conflated with raw results:

| Metric | Formula |
| --- | --- |
| Per-contract P&L (per trade) | `pnl / quantity`, where both known and `quantity > 0` |
| Per-contract total/avg/median | aggregates of the above ("1-contract equivalent") |
| Capital deployed (per trade) | `risk` if present and > 0, else `|premium|`; trades with neither are excluded from capital metrics |
| P&L per $1,000 deployed (per trade) | `pnl / capital · 1000` |
| P&L per $1k (aggregate) | `Σ pnl / Σ capital · 1000` over trades with both |
| Return on risk | `mean(ror)` as exported |
| Equal-weighted trade return | `mean(return_fraction)` — each trade counts once regardless of size |

## Equity curve & drawdown (`analytics/equity.py`)

- **Equity curve**: cumulative `realized_pnl` in close-time order,
  starting from 0 (no account-balance data in Phase 1).
- **Running peak**: `cummax(equity)` clipped at ≥ 0 (the account starts
  at 0, so an immediately negative curve is already a drawdown).
- **Dollar drawdown**: `peak − equity` (≥ 0). **Max drawdown** = its max.
- **Percentage drawdown**: `drawdown / peak · 100` **only where
  peak > 0**; otherwise None (mathematically invalid → fail closed).
- **Drawdown duration**: time from the peak preceding the max-drawdown
  trough to that trough.
- **Recovery duration**: trough to the first point where equity regains
  the prior peak; None while unrecovered.

## MFE / MAE (`analytics/excursion.py`)

Source: Option Alpha `highReturnPct` (MFE) and `lowReturnPct` (MAE),
decimal fractions on the same base as `return_fraction`. Intratrade
excursion is NOT reconstructed from market data in Phase 1.

| Metric | Formula |
| --- | --- |
| Avg/median MFE, MAE | means/medians over non-null values |
| **MFE capture ratio** | `mean(return_fraction) / mean(mfe_fraction)` over trades with `mfe_fraction > 0` (aggregate form — per-trade ratios explode as mfe → 0; unit-invariant) |
| Median per-trade capture | `median(return_fraction / mfe_fraction)` over `mfe_fraction > 0` (robust secondary view) |
| Profit giveback | `mean(mfe_fraction − return_fraction)` over `mfe_fraction > 0` |
| Reached +T | `count(mfe_fraction ≥ T)` for T ∈ {0.05, 0.10, 0.15, 0.20, 0.25, 0.30, 0.50} (i.e. +5%…+50%) |
| Reached-but-closed-flat | `mfe_fraction ≥ 0.05` and `return_fraction = 0` |
| Reached-but-closed-below-5% | `mfe_fraction ≥ 0.05` and `0 < return_fraction < 0.05` |
| Reached-but-closed-negative | `mfe_fraction ≥ 0.05` and `return_fraction < 0` |
| Losers previously profitable | `realized_pnl < 0` and `mfe_fraction > 0` |
| Winners with adverse excursion | `realized_pnl > 0` and `mae_fraction ≤ −T` for T ∈ {0.05, 0.10, 0.20, 0.30, 0.50} |

## Grouped analysis (`analytics/grouping.py`)

`grouped_metrics(df, by)` computes the core + normalized metrics per
group for: `bot_name`, `strategy_family`, `strategy_version`,
`underlying_symbol`, `asset_class`, `instrument_type`, `target_delta`,
`dte_setting`, `dte_at_entry`, `timeframe`, `entry_hour`, `exit_hour`,
`day_of_week`, `month`, `quantity`, `quantity_bucket`, `environment`,
and `tags` (exploded so a trade counts in each of its tags).

Rows with a null group key are excluded — they form no meaningful group.
`compare_groups(df, by, values)` restricts the table to chosen values
(e.g. `target_delta ∈ {0.50, 0.60, 0.65}`, `dte_setting ∈ {0, 1, 2}`,
symbols `SPY/QQQ/NVDA`).

Derived grouping columns (added by `analytics/frames.enrich`):
`entry_hour`/`exit_hour` (wall-clock hour), `day_of_week` (of open),
`month` (`YYYY-MM` of open), `quantity_bucket` (1, 2, 3-4, 5-9, 10+).
