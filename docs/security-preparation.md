# Finance persistence and TickTick: prepared, inactive

As of 2026-10-29. This branch publishes UI and inactive source code only. Netlify's static `echo no-build` deployment does not apply SQL or deploy Supabase functions. No live Supabase table, RLS policy, auth setting, credential or OAuth grant was changed. No personal row was queried, uploaded or migrated. The separate reported 12-table RLS issue remains unresolved.

## Finance migration review

`supabase/migrations/20261029091011_finance_snapshots_owner_scope.sql` was named using the pinned Supabase CLI's `migration new` command, without login or linking a project. It creates only:

- `public.finance_snapshots` and its primary/unique indexes, with manual earnings-versus-worth shape checks, dates/currencies/coverage, bounded numeric values, revision and timestamps.
- Four authenticated owner CRUD policies and one restrictive policy denying anonymous Auth users, absent claims and null identities. Owner authorization uses verified `auth.uid()`, never user metadata.
- Enabled and forced RLS. Revoked all public/anon/authenticated defaults, then granted authenticated SELECT/INSERT/UPDATE/DELETE only. No TRUNCATE or broad inherited privileges.
- One invoker trigger function and update trigger preserving record ID/creation time and advancing revision. Function execution is revoked from browser roles.

The migration is transactional and deliberately fails on existing object names rather than silently replacing objects. Database administrators/service-role operators retain their inherent privileged capabilities; none are exposed to the browser. It does not alter any existing table, auth settings, grants on other tables, default privileges, or credentials. It does not import history or include finance in legacy app snapshots, general backups, AI prompts or telemetry. Financial fields are held only in React state in this preview, including unfinished drafts; reload/sign-out/account changes clear them.

A future client must use the signed-in user's JWT and optimistic `id + revision` updates, report conflicts, and never use a service-role key. Currency conversion, bank connections and transactions are outside this model. The UI currently supports cumulative YTD snapshots and separately dated net-worth balances.

**Smallest next security approval:** approve applying exactly this additive migration to Supabase project `cgbyfooxstxinttfvwzq`, followed by metadata verification and isolated synthetic owner/non-owner/anonymous tests in a disposable test environment. No live user creation or financial test rows are included in that approval. Hosted Auth/PostgREST end-to-end testing needs a separately approved staging environment/test identities if none exist. Only after that verification should separately reviewed client persistence be enabled. The wider 12-table lockdown is a separate permission and remains necessary to secure the existing app overall; this additive migration does not resolve it.

## Isolated database evidence

Run `npm ci --prefix tests/security --ignore-scripts` then `npm test --prefix tests/security`.

PGlite 0.5.13 runs the exact migration in an in-memory PostgreSQL 18.6 engine with synthetic Supabase roles/auth helpers, two fake identities and a legacy sentinel. 45 assertions check owner CRUD, cross-owner reads/update/delete/spoofed insert/upsert, owner transfer, anonymous/missing claims, table privileges, revision conflicts, validation and untouched unrelated records. There is no remote connection. This proves SQL behavior in that engine; it is not a hosted Supabase/Auth/PostgREST test or a claim about the existing project's security. Pinned CLI 2.122.0 and upstream PostgreSQL/Supabase changelog were reviewed; this migration uses core SQL without extensions/custom operators. Hosted version compatibility remains a deployment check.

## TickTick boundary

Prepared server files:

- `_shared/ticktick-adapter.mjs`: fixed `https://api.ticktick.com/open/v1` transport; no redirects, generic errors, bounded timeout, minimal task fields and revision hash.
- `_shared/ticktick-handler.mjs`: bearer authentication, verified permanent owner identity, explicit project/origin allowlists, server gates, rate-limit dependency, verified owner-bound credential resolver, and durable operation-store dependency.
- `ticktick/index.ts`: validates identity via Supabase `/auth/v1/user`; all feature gates remain false, credentials resolve to null, and operation/rate-limit stores remain absent. No browser path imports or calls this endpoint.

Only projects, project data, task reads and task completion are implemented. Completion requires a revision, a unique operation ID, durable reservation, canonical pre-read, POST, canonical readback, and durable recorded outcome. Provider failure, a missing completed record, ambiguous outcomes or store failure cannot return confirmed completion. Replaying a request cannot silently retry a provider write. Revision checking detects prior changes but cannot make the TickTick API transactional: a provider-side race between GET and POST remains possible. Abandoned tasks cannot be completed. Habits, create/delete/reopen, calendar writes and private-chat wakeups are unsupported here.

Thirty synthetic request tests verify disabled defaults, failed/anonymous/other-owner auth, allowlists, input bounds, no credential/provider-body leakage, sanitized reads, completion confirmation, stale revisions, no automatic retry, replay conflicts and missing stores. No live token, account or task was accessed.

**Separate approvals still needed:** provision a dedicated personal API token in an approved server secret store; verify its account is the intended owner; choose allowed projects and preview/production origins; implement and approve durable operation/rate-limit storage; deploy the authenticated function and enable read scope first. Enabling completion requires a further deliberate write gate and a disposable live test task explicitly approved by the user. Do not borrow ChatGPT connector credentials. A personal API token is supported, so a custom OAuth app is optional. A successful app completion updates canonical TickTick; the assistant can later read it through a supported connector. There is no supported automatic private-chat wake bridge in this implementation.

References reviewed 2026-10-29: [TickTick Open API](https://developer.ticktick.com/docs/openapi.md), [personal token option](https://developer.ticktick.com/docs/index.html#/openapi?id=quick-option-create-a-personal-api-token), [Supabase RLS](https://supabase.com/docs/guides/database/postgres/row-level-security), [Supabase anonymous users](https://supabase.com/docs/guides/auth/auth-anonymous), [Supabase CLI migrations](https://supabase.com/docs/reference/cli/supabase-migration-new).
