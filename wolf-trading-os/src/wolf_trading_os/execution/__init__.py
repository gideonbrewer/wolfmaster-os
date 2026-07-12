"""Execution — DELIBERATELY EMPTY (Phase 1 restriction).

Per AGENTS.md rule 13, Phase 1 must contain no order-placement or
order-simulation capability. This package intentionally defines NO
functions, NO classes, and NO interfaces that could place, route,
transmit, or simulate an order.

Future phases will introduce an execution layer here, gated by:
- central risk approval (risk controls have final authority),
- idempotency keys on every order,
- full event logging (signal, decision, order, fill, rejection,
  cancellation, reconciliation),
- explicit paper/live separation with live never the default.

tests/unit/test_no_execution_capability.py enforces that this package
stays empty of executable order paths.
"""
