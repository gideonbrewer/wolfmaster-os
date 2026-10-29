# Mobile companion redesign — review record, 29 October 2026

This revision replaces the long Home with Today and a consistent four-destination navigation. It was tested locally on `companion-today`, based on `d7c865c`. On 29 October 2026 at 12:47:37 UTC, the user approved updating existing draft PR #1 and its automatic review preview. Publication verification is recorded separately after the push. Finance saving remains disabled.

## Design rationale

Today is a starting point: three priorities, one next saved commitment, a single attention summary, and a Wallace handoff. The first priority has stronger hierarchy, secondary priorities remain immediately accessible, and detailed attention or connection information opens in a dismissible sheet. Home has no financial summary, chart, data, entry form, or complete task backlog. The restrained slate/blue palette, readable type, consistent rounded surfaces and generous controls extend the existing app rather than introduce a second product.

| Destination | Purpose | Discoverable detail |
| --- | --- | --- |
| Today | What matters, what is next, what needs attention | Task detail, source status, attention records, editable Wallace context |
| Plan | Turn intention into a day | Schedule, priorities, waiting; existing calendar/focus, weekly horizons, routines and task queue |
| Projects | See work and find its context | All open tasks with search and project drill-down; People, Build & learn, Review & habits, knowledge/connections |
| Finance | Deliberate, separate financial review | Overview, collapsed coverage/trends, dated history, separate entry flow, earlier money workspace |

All available task rows remain accessible; the project lists are not truncated. Existing People, Build, Review, habits, goals, debrief, Sync and planning workspaces remain wired. The old Momentum link now opens the retained momentum component in Review. Earlier Money access is relocated under Finance and retains its existing storage behavior; no records are migrated. Legacy financial controls are not represented as protected by the new finance store.

## Honest assistant and source behavior

Wallace is a manual context handoff. The sheet contains editable priorities, next commitment, attention counts and source freshness. Copy is explicit; the app does not send messages, read Dot history or claim synchronized assistant context. Finance state is never passed to Today or the handoff helper. TickTick and Notion show Not connected. Imported tasks remain read-only, while local completion updates WolfMaster. Empty or stale calendars never imply verified availability.

## Interaction and accessibility

Four fixed bottom destinations use at least 44px touch targets. Browser history and in-app Back preserve route traversal, including planning subtabs and secondary workspaces. Dialogs have an accessible name, Escape dismissal, a focus trap and focus restoration. The mobile layout supports safe-area CSS and reduced-motion preferences. Finance drafts are retained across tabs; saved/session-only status remains explicit, unknown outcomes cannot silently retry, and amounts are masked when the overview remounts.

## Verification and limits

Synthetic offline fixture generated from production primary components; all outgoing data requests are blocked by CSP. It substitutes the App mount and account header, and uses route stubs for legacy secondary screens. Consequently screenshots prove primary layout and routing, not authenticated legacy screens or live integrations.

Phone-width checks at 320, 375, 390 and 430px found no horizontal overflow and no finance component on Today. At a height of 844px, total scroll height was 844px for 375/390/430 and 883px for 320. Bottom navigation targets were at least 63 × 58px. This is a CSS viewport test, not a physical iPhone/Safari safe-area or keyboard test.

Browser functional assertions exercised local completion, imported-task lock, Sources, Wallace editing/focus trap/Escape, Plan priorities and browser Back, Projects all 16 synthetic tasks/filtering, People route/Back, Finance overview/entry, draft retention, session save, edit/cancel, amount masking and clearing on reload. Empty and stale states plus attention disclosure were checked separately. Clipboard transmission was not performed.

Follow-up diagnosis reproduced the identical MutationObserver TypeError on initial load and reload of a fresh, script-free static iframe: no WolfMaster, React, Babel or diagnostic scripts were loaded. This rules out WolfMaster as its cause and points to browser iframe instrumentation; the specific injected script/stack is not exposed by the supported tools. Both page-level error listeners and an observe wrapper in a separate diagnostic fixture recorded no page-world error. The normal top-level synthetic app then passed Finance draft retention, session save and reload checks: draft 125 retained across tabs, one snapshot before reload, zero after reload. It had no runtime exception or captured page error; only the existing Babel large-bundle formatting notice. No application fix was warranted. This iframe tooling issue does not block the tested normal top-level flow. The maintained browser test still reports unattributed errors rather than silently discarding them. Hosted authentication, live APIs, physical iOS and full legacy secondary screens remain outside this synthetic verification.

The local regression suite covers the model, Today composition, executive sync, navigation/handoff boundaries, finance form states, disabled finance client, synthetic store races/conflicts, 45 isolated RLS assertions and 30 TickTick boundary assertions. No hosted database, real finance records, credential changes or live migrations were used. The pre-existing security restrictions and finance activation approvals remain as documented in `finance-persistence-client.md`.

## Reproduce and review

Generate `tests/preview-companion.py OUTPUT_DIR LOCAL_LIB_DIR` using the existing pinned React 18.2.0, ReactDOM 18.2.0 and Babel 7.27.1 bundles. Serve OUTPUT_DIR on loopback only. The `phone-320.html`, `phone-375.html`, `phone-390.html`, `phone-430.html`, `phone-empty.html` and `phone-stale.html` wrappers supply synthetic scenarios.

`tests/companion-mobile.mjs` exports a CUA-native responsive check. `tests/companion-browser.mjs` exports an async generator; supply the supported CUA Tab and call `next()` one stage at a time, allowing browser Back its own turn. These replace the standalone browser launchers. Review screenshots and measured results are in the task-2 `redesign-review` directory.

Screenshots requested for Library contain synthetic records only. The Library prepared-upload helper could not reach its service: DNS failed in the sandbox, then TLS failed with network access. No upload reached preparation/finalization and no Library item is confirmed. The local JPEG files remain available for same-executor transfer. Do not bypass TLS verification.

## Approval boundary

The user approved publication of this reviewed revision to draft PR #1 and its automatic review preview on 29 October 2026 at 12:47:37 UTC. This supersedes the earlier publication restriction for this revision only. Keep draft status, no merge or production promotion. Finance activation remains a separate migration/security test/deployment decision. TickTick credentials and live writes remain unapproved. The denied PR metadata change has not been retried.


## Typography and immediate composer refinement — 29 October 2026

Prepared against published commit `7c0bd4f0238cf01a28d8034a60ff1052f724a1af` after the user's mobile feedback. No publication is included in this preparation.

- A consistent mobile scale replaces the extreme heading/caption contrast: 28px page titles, 18–19px emphasized items/sections, 16px primary text, 13px secondary text and 12px labels/navigation. Form and composer inputs remain at least 16px. Finance stays on its separate tab.
- Today renders the editable Wallace composer immediately below its heading, not behind a launcher or sheet. The single-line field grows up to 128px for longer messages. Copy is explicitly a manual handoff; typing or opening context does not transmit anything. Context review remains optional and excludes Finance.
- Draft state is owned above the tab routes, so tab switches preserve it. It clears on account change or reload and is excluded from legacy saves, backups and export. Clipboard failure retains the draft and provides a manual-copy explanation.
- Narrow Projects utility cards become a readable single-column list rather than three cramped cards.

Passed locally: Babel JSX compilation; new composer hook-simulation tests; existing model, navigation, compact Today/data, executive-sync, finance form/store/boundary and 30-request TickTick boundary suites; `git diff --check`. The maintained browser test was updated for inline typing, optional context review and draft retention.

Browser verification for this refinement is **not completed**. Installed Chromium could not start because its sandbox disallowed process socket creation. A normal escalation attempt failed before execution with a read-only runtime session-path error. The supported cloud browser could not reach the workspace loopback fixture. No security settings or denied paths were changed; no retry bypass was attempted. Responsive widths 320/375/390/430, physical iOS keyboard, text enlargement, final overall height and screenshots still require browser QA. The previous revision's successful rendering does not prove this refinement's layout.
