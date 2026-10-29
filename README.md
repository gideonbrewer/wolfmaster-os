# WolfMaster OS

A single-file personal operating system — dark/lime command-center UI with
Supabase auth + persistence. Standalone app (separate from Purple Atlas).

## Run / deploy

It's one static file, no build step.

```bash
# local preview
python3 -m http.server 8000      # open http://localhost:8000

# deploy: drag this folder into Vercel/Netlify, or point any static host at it.
# (index.html is at the repo root, so it deploys as-is.)
```

## Architecture

- **Tabs:** NOW, PLAN, PEOPLE, BUILD, REVIEW. Fitness and Money still exist in
  code but are parked off-nav.
- **Auth + data:** Supabase REST (`SUPABASE_URL` / `SUPABASE_ANON_KEY` near the
  top of the `<script type="text/babel">` block). Session is cached in
  `localStorage` (`wm_session`); all app data persists to Supabase tables, not
  localStorage.
- **Styling:** base design system (`.glass`, `.card`, `.cc-*`) plus a
  `#wm-polish` layer (last in `<head>`) adding focus rings, select chevrons,
  button/hover states, elevated cards, custom scrollbars, dark native pickers.

## AI Command Brief

The legacy generated-brief implementation remains in `supabase/functions/ai-brief`.
The companion Home currently shows an explicitly labeled local summary and does
not call this endpoint until the data path is approved. The endpoint receives an
app-generated digest; it does not access the assistant conversation.

Legacy setup reference (do not execute before security and deployment approval):

```bash
supabase login
supabase link --project-ref cgbyfooxstxinttfvwzq
supabase secrets set OPENAI_API_KEY=sk-xxxxx
supabase functions deploy ai-brief
```

Run `supabase/sql/ai_briefs.sql` once in the Supabase SQL editor to create the
daily cache table and RLS policy.

## Constraints for future edits

- Don't break Supabase auth/persistence; don't move persisted data to localStorage.
- Keep Top 3 / Weekly Top 5 edit/delete/complete behavior intact.
- `#wm-polish` is presentational only — keep it last in the cascade.

## Focused NOW screen

NOW defaults to Daily 3, the next saved timed calendar item/focus block today,
then dated or explicitly urgent saved tasks and follow-ups. Shared/imported
calendar presence is not an attendance confirmation. Sync status is shown when
no next timed item is available; this is not a claim of verified free time.
Life Clock, AI brief/counters, timeline, execution suggestions and momentum stay
in the closed-by-default Details drawer. PLAN/PEOPLE/BUILD/REVIEW are unchanged.
Legacy unchanged demo rows are excluded from NOW projections without deleting
stored records. Edited legacy rows remain eligible. Review/replace untouched
sample Daily 3 entries in PLAN before adding from NOW, preserving list capacity.

Focused regression tests (no account or network access):

```bash
node tests/now-focus.test.mjs
node tests/executive-sync.test.mjs
```

### Isolated browser QA

Generate a disposable mock-data preview without signing in or loading the live
App shell. It reuses the production NOW components and CSS, replaces only the
root mount, and blocks network connections/form submissions with CSP:

```bash
python3 tests/preview-now.py /tmp/wolfmaster-now-preview
python3 -m http.server 8000 --directory /tmp/wolfmaster-now-preview
```

Open `/` for populated data, `/?scenario=empty` for empty/disconnected states,
`/?scenario=demo` for legacy Daily 3 suppression, or `/mobile.html` for a 390px
iframe viewport. Fixture changes are in-memory and reset on reload. This checks
NOW UI behavior, not authenticated Supabase persistence or other app tabs.

## Home companion and manual Finance preview

The local companion version replaces the hidden NOW details layout with visible source status, brief, schedule, tasks by project, waiting-on items and a Home finance snapshot. Finance is **session-only, test amounts only** until secure persistence is approved. TickTick is the canonical task/habit tracker; live writes and the assistant event bridge are not connected. See [implementation, safety boundaries and validation](docs/companion-first-version.md).
