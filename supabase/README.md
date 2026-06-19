# WolfMaster OS — Supabase backend

## AI Command Brief

The NOW screen's "AI Command Brief" is written by Claude from your own day data.
The Anthropic API key never touches the public front end — it lives as a Supabase
secret and is used only inside the `ai-brief` Edge Function.

```
WolfMaster (browser) --auth token--> ai-brief Edge Function --API key--> Claude API
     ^------------------------- brief text -----------------------------------'
```

### One-time setup

1. **Anthropic key** — console.anthropic.com → API Keys → create (`sk-ant-...`).
   Briefs are tiny (~1-2K in, ~300 out, ≤1/day) so spend is pennies/month.

2. **Store it as a Supabase secret** (never in the repo):
   ```bash
   supabase login
   supabase link --project-ref cgbyfooxstxinttfvwzq
   supabase secrets set ANTHROPIC_API_KEY=sk-ant-xxxxx
   ```

3. **Create the cache table** (≤1 brief/user/day). Run the migration:
   ```bash
   supabase db push          # applies migrations/20260619000000_ai_briefs.sql
   ```
   …or paste that file into the SQL editor.

4. **Deploy the function** (JWT verification is on by default — only signed-in
   users can call it):
   ```bash
   supabase functions deploy ai-brief
   ```

### Model & cost

Defaults to `claude-haiku-4-5` (fast, cheapest tier) — perfect for a short daily
brief. For sharper phrasing, change `MODEL` in `functions/ai-brief/index.ts` to
`claude-sonnet-4-6`. With ≤1 generation/day plus the de-dup cache, cost is pennies
per month. Confirm current per-token pricing in the Anthropic console.

### Behavior / safety

- The browser sends a compact **digest** of today's data (Top 3, attention signals,
  today's calendar, momentum) — titles/short text only, not notes.
- One brief per user per day; the function de-dupes by date + input hash. The ↻
  button on NOW forces a fresh generation (`force: true`).
- If Claude is unreachable, the request fails, or you're signed out, NOW keeps the
  original templated brief — a Claude outage never breaks the screen.
