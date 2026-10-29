# Companion first version — local handoff, 2026-10-29

Branch `companion-today` starts at `e4be9ff`, the draft PR #1 NOW preview, on top of production `40a6bcf`. The original checkout at `/Users/gideonbrewer/Desktop/Ventures/WolfMaster/wm-current` remains untouched. Nothing was pushed, merged, or deployed.

## What is implemented

Home now presents a visible grounded summary, Daily 3, the next available calendar item, today's saved schedule, waiting-on records, urgency, financial picture, and the full open-task projection grouped by project with a filter. Source availability is always visible. The prior hidden Details composition is superseded; legacy screens and saved records remain available. No fake meetings count, free-time inference, momentum score, or financial history is introduced.

The brief is an explicitly labeled local summary. The existing OpenAI endpoint remains in the repository but Home does not invoke it: sending the current digest through an unreviewed data path is not enabled. It does not access the assistant's private conversation or work state.

Task identity/projection functions are in `assets/companion/model.js`. TickTick is an accepted canonical source; imports preserve source project ID. Imported priority copies derive displayed completion/title from their referenced canonical projection. Home completion/edit is disabled for imported records; App-level guards prevent silent local mutation through other priority/task controls. Removing a priority from Daily 3 is local attention management, not source deletion. Legacy local records retain local editing; they are labeled WolfMaster-only. New Home task capture is hidden; existing PLAN is preserved for legacy work.

The canonical completion contract requires authorization, a verified connection, security approval, an explicit mutation gate, source/project IDs and a request ID. It reports confirmed only after reading the exact same record/value back. Exceptions and mismatches return unconfirmed, never a local success. There is no instantiated live TickTick adapter, no enabled mutation gate and no real task change.

Calendar `syncedAt` is retained in state, cloud snapshot shapes and restore paths. Home labels timestamps over one hour old or any failed-sync snapshot stale, updates this state each minute, and treats missing timestamps as unknown. A saved URL alone is not Synced. Scheduling actions clearly create WolfMaster-only holds. Google OAuth remains read-only. The existing provider selection, permissions and time-zone behavior are not reconfigured.

## Finance contract

The new Finance tab is a manual-entry preview. Its `financeEntries` state is never included in the existing snapshot, local recovery, backups, cloud saves or AI digest. It clears on reload/sign-out. Users are explicitly told to use test amounts until secure saving is available. It does not read or migrate the legacy `money` payload, populate values from conversation, connect accounts or upload financial data.

Each manual entry has `kind`, ISO date, currency, coverage description and source `manual`:

- `earnings`: cumulative totals from January 1 through the as-of date: gross work income; consulting/business income net of business expenses (exclude work income); bitcoin mining revenue and expenses; net realized investment gain/loss; unrealized YTD investment gain/loss. Blank is unknown; an entered zero is a real zero. Net mining is included only when both revenue and expenses are supplied. Negative consulting and investment results are supported.
- `worth`: assets and liabilities at that date. Both are required, including explicit zero. Net worth equals assets minus liabilities and is never added to earnings.

One entry per kind/date/currency; re-entry replaces that dated snapshot. Home uses the latest snapshot of each kind in the selected calendar year/currency. It never sums cumulative YTD snapshots or currencies, adds account balances to income, or treats transfers, contributions, deposits or investment sale proceeds as earnings. Unrealized gains are separate from the earnings subtotal. USD/EUR/GBP/CAD are separate reporting buckets, with no FX conversion.

Charts use actual dated snapshots, with time-proportional spacing, accessible endpoint descriptions and a table of values. At least two snapshots with identical coverage and reported categories are required. Coverage changes show an explanatory empty state. Amounts/trends start hidden on each screen; as-of and coverage remain visible. The entry form itself exposes draft amounts, so it is not a security boundary.

## Secure persistence design — prepared, not applied

Do not reuse the known-unsecured `money` path. After the separately pending security review and user approval:

1. Create an owner-scoped `finance_snapshots` table with UUID key, authenticated owner, kind, date, currency, coverage, validated numeric payload, schema version and timestamps. Enforce unique `(user_id, kind, as_of_date, currency)`. Do not put financial payloads into general dashboard backups or AI prompts.
2. Enable RLS before any records exist. Require `auth.uid() = user_id` for SELECT/INSERT/UPDATE/DELETE with both USING and WITH CHECK where appropriate. Deny anonymous access. Verify with two isolated users and an anonymous client, including attempts to change ownership and access another owner's row.
3. Use an authenticated server boundary or approved user-scoped API, server validation, concurrency/version checks and minimal audit metadata without amounts. Keep service credentials server-only. Verify logs, exports, recovery behavior, retention and deletion before admitting real data.
4. Obtain explicit approval for deployment and migration. Test with isolated fixtures first. Only then replace the in-memory store with the approved repository and offer intentional migration of user-selected legacy values.

No SQL, RLS, auth, credentials, permissions or live table changes were made in this task.

## Remaining gates

- **Security approval pending:** review/approve the existing Supabase lockdown proposal (12 public tables reported without RLS), implement separately and verify access boundaries before real financial entry/storage or generated briefs. The existing legacy app persistence was preserved, not certified safe.
- **TickTick connection/authorization:** identify a supported task and habit API/integration, obtain only approved grants, implement pull and mutation endpoints with canonical IDs/revisions and reconciliation. Habit coverage must be verified independently. Do not infer that tasks imply habit access. Test approved isolated records in both directions before calling it two-way.
- **Assistant visibility:** a supported event bridge or verified polling/import path is required. A database write does not cause this private chat to learn about it. No bridge exists here.
- **Calendar scope:** user-approved personal calendars only. No House official mail, forwarded official records or restricted calendars were ingested. A fresh snapshot does not establish complete account coverage. Google write access would require separate authorization and implementation.
- **Publishing:** explicit authorization is still required to push, open/update a PR, merge or deploy this branch. No new financial definition decision is needed for this preview; report whether the chosen gross-work/net-business convention fits before real use.

## Verification

No package manifest, production bundler, TypeScript project, or lint configuration exists: the app is a static React/Babel page. The complete production JSX is transpiled with the existing pinned Babel 7.27.1; pure JS uses Node syntax checks. Tests exercise production model functions rather than copied implementations (the legacy executive-sync test predates this work).

```
node --check assets/companion/model.js
node tests/companion-model.test.cjs
node tests/now-focus.test.mjs
node tests/executive-sync.test.mjs
git diff --check
```

`tests/preview-companion.py` creates an isolated fixture using production UI functions and replaces only the App mount. It requires local copies of the exact existing React 18.2.0, ReactDOM 18.2.0, and Babel 7.27.1 script assets. The generated preview enforces `connect-src 'none'`; the browser test additionally aborts any non-localhost request. No auth, live account or personal rows are used.

```
python3 tests/preview-companion.py ../preview /tmp/wolfmaster-qa-libs
python3 -m http.server 8765 --bind 127.0.0.1 --directory ../preview
PLAYWRIGHT_PATH=/path/to/playwright node tests/companion-browser.cjs
```

Browser checks cover desktop 1440px and mobile 390px, no horizontal overflow, imported completion lock, local completion, canonical projection deduplication, full project list/filter, manual earnings/net worth → Home aggregation, hidden amounts, real dated chart points, reload clearing, empty/stale states, zero runtime exceptions and zero external requests. Evidence is in `qa/`. These are fixture tests, not a live task-sync loop or production security test.
