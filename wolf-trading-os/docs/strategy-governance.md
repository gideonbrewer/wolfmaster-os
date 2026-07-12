# Strategy Governance (Champion / Challenger)

Governs how strategy variants are evaluated and promoted. Phase 1
provides the measurement side: version-aware analytics that make
challenger comparisons honest. AGENTS.md rule 10 applies throughout:
**no strategy version may promote itself into production.**

## Identity and versioning

- Every strategy has a family (e.g. "Hulk"), a name, and a version
  (e.g. `v2`). The canonical trade model carries all three, so results
  are always attributable to an exact variant.
- A material change to logic or parameters (delta target, DTE,
  sizing, timeframe) is a **new version**, not an edit in place.

## Champion / challenger process

1. **Champion**: the currently promoted version of a strategy family.
2. **Challenger**: a new version runs in paper (or at minimum-size
   allocation, in later phases) alongside the champion, never replacing
   it implicitly.
3. **Comparison** uses quantity-normalized metrics — per-contract P&L,
   P&L per $1,000 deployed, equal-weighted returns, profit factor,
   expectancy, max drawdown, MFE capture — never raw dollars, which
   reward the variant that merely sized larger.
4. **Minimum evidence**: a challenger needs a pre-declared sample size
   and evaluation window before comparison is meaningful; peeking early
   and promoting on a hot streak is prohibited.
5. **Promotion is a recorded human decision**: who, when, on what
   evidence, in `docs/decisions.md` (or a dedicated log in later
   phases). Demotion follows the same path.
6. **Rollback**: the previous champion's exact version stays available
   for immediate reinstatement.

## Phase 1 support

- Bot-name parsing extracts family/version/delta/DTE/sizing so imported
  history is comparable across variants.
- Grouped analytics by `strategy_version`, `target_delta`,
  `dte_setting`, and `environment` (live vs paper) provide the
  challenger scoreboard.
