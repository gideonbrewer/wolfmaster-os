# Risk Policy (Principles)

Phase 1 contains no risk engine because nothing can trade. These
principles govern the future central risk layer and constrain every
later design decision. They expand AGENTS.md rules 3, 4, and 14.

## Authority

1. The central risk engine has **final authority** over every trade
   request. Its rejection cannot be overridden by a strategy, scheduler,
   retry loop, or operator convenience flag.
2. Strategies request; risk authorizes; execution (future) merely
   carries out authorized instructions. No shortcut path may exist.
3. Risk decisions are logged with full inputs and reasons
   (AGENTS.md rule 9) so every authorization is reconstructible.

## Fail-closed defaults

4. Missing, stale, malformed, or contradictory data ⇒ **reject**.
5. Capital-related uncertainty (unknown balance, unknown position,
   unreconciled broker state) ⇒ **no action** and an alert.
6. If risk limits cannot be evaluated (e.g. the limits store is
   unreachable), the answer is rejection, not a cached approval.

## Limit structure (future)

7. Limits will be layered: per-trade, per-strategy, per-symbol,
   per-asset-class, and portfolio-wide. The most restrictive applies.
8. Aggregate exposure is computed against **reconciled** state, not
   intended state.
9. Kill-switch: a single, always-available control halts all future
   order flow; it requires no data dependencies to engage.

## Environment separation

10. Paper and live risk configurations are distinct and never shared by
    default; live limits are never inferred from paper settings
    (AGENTS.md rules 1 and 12).
