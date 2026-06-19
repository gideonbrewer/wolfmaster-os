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

- **Tabs:** NOW, PLAN, PEOPLE, REVIEW, MORE (MORE = Build, Purple Atlas lane,
  Fitness, Money, Reflect).
- **Auth + data:** Supabase REST (`SUPABASE_URL` / `SUPABASE_ANON_KEY` near the
  top of the `<script type="text/babel">` block). Session is cached in
  `localStorage` (`wm_session`); all app data persists to Supabase tables, not
  localStorage.
- **Styling:** base design system (`.glass`, `.card`, `.cc-*`) plus a
  `#wm-polish` layer (last in `<head>`) adding focus rings, select chevrons,
  button/hover states, elevated cards, custom scrollbars, dark native pickers.

## Constraints for future edits

- Don't break Supabase auth/persistence; don't move persisted data to localStorage.
- Keep Top 3 / Weekly Top 5 edit/delete/complete behavior intact.
- `#wm-polish` is presentational only — keep it last in the cascade.
