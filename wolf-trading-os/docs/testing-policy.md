# Testing Policy

AGENTS.md rule 11: material changes require tests. This document defines
what that means here.

## Tiers

1. **Unit tests** (`tests/unit/`) — pure logic, no I/O, no database.
   Run in every CI job and locally with `pytest tests/unit`.
   Cover: value parsing, header/schema validation, bot-name parsing,
   fingerprinting, row normalization, every analytics formula, CLI
   gating, and the no-execution tripwire.
2. **Integration tests** (`tests/integration/`, marker `integration`) —
   real PostgreSQL. Each session creates a scratch database, migrates it
   with Alembic, and drops it afterwards. Cover: migration up/down
   cycles, schema shape (including the fingerprint UNIQUE constraint),
   full import flows (single/multi-file, overlap, in-file duplicates,
   malformed rows, missing columns), field-level persistence
   round-trips, and DataFrame analytics loaded from the database
   (dashboard-path parity).

## Rules

- **Formulas are contracts**: every metric in
  `docs/analytics-definitions.md` has a unit test with hand-computed
  expected values. Changing a formula changes doc + test + code in one
  commit.
- **Fixtures are realistic but synthetic**: Option Alpha CSV fixtures in
  `tests/fixtures/` mirror the real export schema with invented data.
  Never commit real account exports.
- **Fail-closed paths are tested**, not just happy paths: malformed
  rows, missing columns, contradictory markers, empty inputs,
  non-development reset attempts.
- **The no-execution tripwire**
  (`tests/unit/test_no_execution_capability.py`) must stay in place for
  all of Phase 1; weakening it requires a decision-log entry.
- **CI gates**: ruff lint, ruff format check, mypy (strict), unit tests,
  and PostgreSQL-backed integration tests all must pass on every push
  and pull request. All commands run identically locally (see README).

## Commands

```bash
pytest tests/unit                       # fast, no DB
pytest tests/integration -m integration # needs PostgreSQL
pytest                                  # everything
ruff check . && ruff format --check .
mypy
```
