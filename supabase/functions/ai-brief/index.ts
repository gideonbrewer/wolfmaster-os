// WolfMaster OS — AI Command Brief Edge Function
//
// Generates a short, grounded daily brief with Claude from the user's own day
// data. The Anthropic API key lives here as a Supabase secret (ANTHROPIC_API_KEY)
// and never touches the public front end. The browser calls this function with
// the user's Supabase auth token; Supabase verifies the JWT, we identify the
// user, then call Claude and cache one brief per user per day.
//
// Deploy:  supabase functions deploy ai-brief
// Secret:  supabase secrets set ANTHROPIC_API_KEY=sk-ant-xxxxx

import "jsr:@supabase/functions-js/edge-runtime.d.ts";
import { createClient } from "jsr:@supabase/supabase-js@2";

const cors = {
  "Access-Control-Allow-Origin": "*",
  "Access-Control-Allow-Headers": "authorization, apikey, content-type",
  "Access-Control-Allow-Methods": "POST, OPTIONS",
};

// Fast + cheap; perfect for a short daily brief. Swap to claude-sonnet-4-6 for
// richer phrasing/prioritization if you want it sharper (still cheap at this size).
const MODEL = "claude-haiku-4-5";

Deno.serve(async (req) => {
  if (req.method === "OPTIONS") return new Response("ok", { headers: cors });
  try {
    // 1. Identify the user from their Supabase token (Supabase verifies the JWT).
    const supabase = createClient(
      Deno.env.get("SUPABASE_URL")!,
      Deno.env.get("SUPABASE_ANON_KEY")!,
      { global: { headers: { Authorization: req.headers.get("Authorization")! } } },
    );
    const { data: { user } } = await supabase.auth.getUser();
    if (!user) return json({ error: "unauthorized" }, 401);

    const { digest, force } = await req.json();
    const today = new Date().toISOString().slice(0, 10);
    const inputHash = await sha256(JSON.stringify(digest));

    // 2. Serve the cached brief unless data changed or a refresh was forced.
    if (!force) {
      const { data: cached } = await supabase
        .from("ai_briefs").select("brief,input_hash")
        .eq("user_id", user.id).eq("date", today).maybeSingle();
      if (cached && cached.input_hash === inputHash) {
        return json({ brief: cached.brief, cached: true });
      }
    }

    // 3. Call Claude.
    const apiKey = Deno.env.get("ANTHROPIC_API_KEY");
    if (!apiKey) return json({ error: "missing_api_key" }, 500);

    const r = await fetch("https://api.anthropic.com/v1/messages", {
      method: "POST",
      headers: {
        "x-api-key": apiKey,
        "anthropic-version": "2023-06-01",
        "content-type": "application/json",
      },
      body: JSON.stringify({
        model: MODEL,
        max_tokens: 350,
        system:
          "You are WolfMaster, a terse personal chief-of-staff. Write a 2-4 sentence command brief for the operator's day. Be specific and grounded ONLY in the data provided — never invent tasks, names, numbers, or events. Lead with what matters most. Optionally end with one sharp suggestion. No greetings, no filler, no markdown.",
        messages: [{ role: "user", content: buildPrompt(digest) }],
      }),
    });
    if (!r.ok) return json({ error: "claude_failed", detail: await r.text() }, 502);
    const data = await r.json();
    // Refusals (stop_reason "refusal") and any non-text first block fall through
    // to an empty string, which the front end treats as "keep the templated brief".
    const brief = (data?.content?.[0]?.type === "text" ? data.content[0].text : "").trim();

    // 4. Cache and return.
    if (brief) {
      await supabase.from("ai_briefs").upsert({
        user_id: user.id, date: today, input_hash: inputHash, brief,
      });
    }
    return json({ brief, cached: false });
  } catch (e) {
    return json({ error: String(e) }, 500);
  }
});

function json(body: unknown, status = 200) {
  return new Response(JSON.stringify(body), {
    status,
    headers: { ...cors, "content-type": "application/json" },
  });
}

async function sha256(s: string) {
  const buf = await crypto.subtle.digest("SHA-256", new TextEncoder().encode(s));
  return [...new Uint8Array(buf)].map((b) => b.toString(16).padStart(2, "0")).join("");
}

// Build a compact, grounded prompt from the digest the NOW screen assembles.
function buildPrompt(d: any) {
  const m = d?.metrics ?? {};
  return [
    `Today: ${new Date().toDateString()}`,
    `Top 3 today: ${fmtTop3(d?.top3)}`,
    `Attention / overdue signals: ${fmtList(d?.attention)}`,
    `People needing attention: ${fmtList(d?.people)}`,
    `Today's calendar: ${fmtList(d?.events)}`,
    `Top 3 progress: ${m.top3Done ?? 0}/${m.top3Total ?? 0}`,
    `Meetings today: ${m.meetings ?? 0}`,
    `Replies awaited: ${m.awaitingReplies ?? 0}`,
    `Momentum score: ${m.momentum ?? "n/a"}${m.momentumWord ? ` (${m.momentumWord})` : ""}`,
    `Suggested next action (from the app's heuristic): ${d?.recommendedNext ?? "none"}`,
  ].join("\n");
}

function fmtTop3(a: any) {
  if (!Array.isArray(a) || !a.length) return "none";
  return a.map((x) => `• ${x?.text ?? x}${x?.done ? " (done)" : ""}`).join("  ");
}

function fmtList(a: any) {
  if (!Array.isArray(a) || !a.length) return "none";
  return a
    .map((x) => `• ${typeof x === "string" ? x : x?.text || x?.title || x?.name || ""}`)
    .filter((s) => s.trim() !== "•")
    .join("  ") || "none";
}
