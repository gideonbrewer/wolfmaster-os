# Execution Policy (Principles)

**Phase 1 has no execution capability whatsoever** — no order
placement, routing, transmission, or simulation, and no broker
connectivity (AGENTS.md rule 13, enforced by
`tests/unit/test_no_execution_capability.py`). This document records the
principles that will govern the execution layer when a future phase
introduces one.

## Non-negotiables inherited from AGENTS.md

1. **Live is never the default** (rule 1). Reaching a live account
   requires explicit, affirmative, environment-scoped configuration.
2. **Only risk-authorized instructions execute** (rules 2–3). The
   execution layer accepts input exclusively from the central risk
   engine's approval output.
3. **Idempotency everywhere** (rules 6–7). Every order carries a
   deterministic idempotency key derived from its originating
   signal/decision; retries and replays must be provably safe.
4. **Reconciliation is mandatory** (rule 8). Internal order/position
   state is a claim to be verified against the broker on a schedule and
   after every disturbance (disconnect, restart, rejection).
5. **Everything is logged** (rule 9): order submission, acknowledgment,
   fill, partial fill, rejection, cancellation, and every
   reconciliation delta — as structured JSON events.

## Additional principles

6. State transitions must be explicit (a typed order state machine);
   unknown broker states map to a quarantine state that blocks further
   automation on the affected instrument, not to a guess.
7. Paper and live execution paths share code but never share
   credentials, endpoints, or configuration files (rule 12).
8. Order capability arrives interface-first, with contract tests and a
   paper-only rollout gate, before any live adapter is written.
