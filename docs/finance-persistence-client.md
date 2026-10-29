# Finance persistence client — local preparation, disabled

The build-time `FINANCE_PERSISTENCE_ENABLED` constant in `index.html` remains **false**. There is no URL, browser-storage or global runtime override. The disabled path does not construct a finance client or call Auth/Data APIs. The reviewed client may ship in the approved draft preview with its gate disabled; publishing the code does not activate finance saving.

## Behavior when separately activated

`assets/companion/finance-store.js` uses the existing public API key and signed-in user's bearer token against the same Supabase origin. Before every read or write, `/auth/v1/user` must confirm the expected owner and explicitly report `is_anonymous: false`. Requests use `no-store`, omit cookies, refuse redirects and have a 15-second abort timeout. No service-role key, credential provisioning, logging, local storage or session storage is added. RLS remains the authoritative server boundary; the client gate is a rollout control, not authorization.

Reads specify the owner, select an explicit column list and paginate in stable ID order until empty. Errors or the 10,000-record safety limit fail the load rather than showing a truncated history as complete. No save is allowed until loading succeeds. Account changes clear the displayed state and draft; disposed or stale-session responses cannot populate another account.

The UI's insert-or-replace action is implemented as INSERT for a new natural key, or UPDATE filtered by owner, ID and the displayed revision. It deliberately does not use an unconditional PostgREST upsert. Unique-key races and zero-row revision updates are conflicts. The server trigger advances revision; the returned representation must match the submitted fields, owner, identity and expected revision before the UI says Saved. The existing migration is unchanged.

Only confirmed rows update the Finance overview and history. Saving locks the draft controls. Failure preserves the draft. Unknown outcomes block further writes until a fresh account read reconciles the same natural key. Matching saved values can be confirmed without resending; differing or absent records require the user to review the result and explicitly retain the draft against that version before pressing Save again. CAS protects against changes after that review. There is no automatic write retry, automatic background save, durable delete action, or offline queue.

Form drafts and status survive tab navigation. Unsaved edits never inherit a previous Saved label. Closing with unsaved data prompts the browser's unload warning where supported; sign-out blocks an in-flight save and otherwise asks before discarding a draft/unresolved result. Mobile operating systems may terminate tabs without firing unload, so the page explicitly warns that unsaved drafts can be lost. No durable draft storage is claimed.

Finance remains excluded from the explicit legacy snapshot allowlist, local recovery, general export/backup, legacy sync and AI request path. The financial picture is confined to Finance. Today receives no finance props, and the Wallace handoff excludes finance entries. The earlier money workspace remains separate, reachable under Finance, with its existing storage behavior; no legacy data is migrated or newly protected by this client.

## Synthetic verification

- `node tests/security/finance-store.test.cjs`: default zero-network gate, verified permanent owner, POST insert, revision-filtered PATCH, stale draft/concurrent insert conflicts, explicit rebase, lost-response reconciliation without retry, error retention, validation, pagination, disposal and account races.
- `node tests/security/finance-ui.test.cjs`: production form handlers/rendered React element tree with in-memory hooks; saving locks, confirmed-only rows, failed draft retention, tab remount, conflict controls and accurate save labels. Set `WM_BABEL_PATH` to a local Babel standalone 7.27.1 bundle if it is not at `/tmp/wolfmaster-qa-libs/babel.js`.
- Existing `npm test --prefix tests/security`: unchanged migration's 45 PGlite RLS assertions, TickTick boundary tests and expanded disabled-gate/legacy/AI boundary checks.
- Production JSX compilation and existing model/NOW/executive-sync regressions.

All test amounts, identities and tokens are synthetic. No hosted database, user rows or credentials are accessed. The transport tests emulate Auth/PostgREST responses; they do not prove a real hosted Auth/PostgREST round trip, cross-device persistence or physical iPhone behavior.

## Smallest activation scope

1. Separately approve and apply exactly the additive `supabase/migrations/20261029091011_finance_snapshots_owner_scope.sql` already under review. Verify its owner policies, restrictive anonymous-user policy, privileges, constraints and revision trigger against the target project's PostgreSQL/API configuration. This patch adds no SQL change.
2. Approve a disposable hosted test environment and two synthetic permanent test identities, plus an anonymous test identity, to verify the client's real Auth/Data API path: owner insert/read/update across reloads, cross-owner/anonymous denial, revision conflict, token expiry and response-loss reconciliation. No real financial records are needed. Migration approval alone does not authorize creating live users or rows.
3. After those checks, separately approve one reviewed deployment with only the finance build gate enabled for the intended environment. The exact deployment target must be named. Existing public-key/user-session wiring is sufficient; no new secret or service-role credential is required. Confirm the remaining legacy-table security issue separately before authorizing real financial use of the overall application.

The 29 October 2026 review-preview approval permits publishing this disabled client alongside the mobile redesign to existing draft PR #1. It does not authorize finance activation, production deployment, live migration, credential changes, legacy-table changes, finance in AI, or TickTick activation. The PR metadata update remains unperformed.

References checked: [Supabase Auth getUser](https://supabase.com/docs/reference/javascript/auth-getuser), [Data API](https://supabase.com/docs/guides/api), [returned mutation rows](https://supabase.com/docs/reference/javascript/using-modifiers-select), [HTTP TLS changelog](https://supabase.com/changelog/cbc-tls-ciphers-deprecated). Existing REST usage is preserved without adding a package dependency.
