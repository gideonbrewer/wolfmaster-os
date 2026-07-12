# AGENTS.md — Permanent Engineering Rules

These rules bind every contributor, human or AI, across all phases of
Wolf Trading OS. They are not style preferences; violating them is a
defect. Each rule lists how it is (or will be) enforced.

## The rules

1. **Live trading must never be the default.**
   Any future execution capability must require explicit, affirmative
   configuration to touch a live account. Absence of configuration means
   paper — or better, nothing.

2. **A strategy may request a trade but may not authorize execution.**
   Strategies emit `TradeRequest`s (see `wolf_trading_os.strategies`).
   Authorization is exclusively the risk layer's decision. No strategy
   code path may reach an execution interface directly.

3. **Central risk controls have final authority.**
   Every future order must pass through the central risk engine
   (`wolf_trading_os.risk`), and its rejection is not overridable by
   strategy, scheduler, or operator convenience flags.

4. **Missing, stale, malformed, or contradictory data must fail closed.**
   Phase 1 already applies this: rows without identity-critical fields
   are rejected; contradictory live/paper markers resolve to UNKNOWN;
   percentage drawdown is omitted where mathematically invalid; values
   are never guessed.

5. **Credentials must never be committed.**
   Configuration comes from the environment (`.env`, never committed;
   `.env.example` is the template). Anything resembling a secret in a
   commit is an incident, not a cleanup task.

6. **Duplicate signals must never create duplicate future orders.**
   Phase 1 enforces the pattern at the import layer: deterministic
   fingerprints with a database-level unique constraint. Future signal
   handling must follow the same idempotent design.

7. **Every future order must have an idempotency key.**
   The key must be deterministic from the originating signal/decision so
   that retries and replays are safe.

8. **Broker state must be reconciled against internal state.**
   Future phases must treat internal records as claims to be verified
   against the broker, on a schedule and after every disturbance. The
   read-only `BrokerStateReader` contract in `wolf_trading_os.brokers`
   is the seam reserved for this.

9. **Every future signal, decision, order, fill, rejection, cancellation,
   and reconciliation event must be logged.**
   Structured JSON logging (`wolf_trading_os.logging`) exists from
   Phase 1; the import pipeline already logs every batch outcome.

10. **New strategy versions may not promote themselves into production.**
    Promotion is a human decision following the champion/challenger
    process in `docs/strategy-governance.md`.

11. **Material changes require tests.**
    CI runs ruff, mypy, and the full pytest suite (including
    PostgreSQL-backed integration tests) on every push and pull request.
    A material change without tests does not merge.

12. **Paper and live environments must remain explicitly separated.**
    The `environment` dimension (live/paper/unknown) is first-class in
    the canonical trade model and analytics. Future runtime environments
    must be configured explicitly (`WTOS_ENVIRONMENT`), never inferred.

13. **Phase 1 must contain no order-placement or order-simulation
    capability.**
    The `execution/` package is deliberately empty of interfaces and
    implementations. `tests/unit/test_no_execution_capability.py` is a
    tripwire that fails the build if order-capable symbols, broker
    client imports, or broker dependencies appear.

14. **Capital-related uncertainty must result in no action.**
    Whenever the system cannot establish position, balance, or risk
    state with confidence, the correct behavior is to do nothing and
    alert — never to act on an assumption.

## Working method expected of agents

- Inspect before changing; plan before implementing.
- Work incrementally and run the relevant tests after each material
  module (`pytest`, `ruff check .`, `ruff format --check .`, `mypy`).
- Never claim something works without having executed the command that
  proves it.
- Correct failures rather than hiding, skipping, or ignoring them.
- Record material design decisions in `docs/decisions.md`.
- Keep scope within the current phase; future capability arrives as
  interfaces first, implementations later, tests always.
