import "jsr:@supabase/functions-js/edge-runtime.d.ts";
import { createClient } from "jsr:@supabase/supabase-js@2";

const cors = {
  "Access-Control-Allow-Origin": "*",
  "Access-Control-Allow-Headers": "authorization, apikey, content-type",
  "Access-Control-Allow-Methods": "POST, OPTIONS",
};

const MODEL = "claude-haiku-4-5-20251001";

Deno.serve(async (req) => {
  if (req.method === "OPTIONS") return json({ ok: true });
  if (req.method !== "POST") return json({ error: "method_not_allowed" }, 405);

  try {
    const supabase = createClient(
      Deno.env.get("SUPABASE_URL")!,
      Deno.env.get("SUPABASE_ANON_KEY")!,
      { global: { headers: { Authorization: req.headers.get("Authorization") || "" } } },
    );

    const { data: { user }, error: userError } = await supabase.auth.getUser();
    if (userError || !user) return json({ error: "unauthorized" }, 401);

    const { digest, force = false } = await req.json();
    if (!digest || typeof digest !== "object") return json({ error: "missing_digest" }, 400);

    const today = new Date().toISOString().slice(0, 10);
    const inputHash = await sha256(JSON.stringify(digest));

    if (!force) {
      const { data: cached } = await supabase
        .from("ai_briefs")
        .select("brief,input_hash")
        .eq("user_id", user.id)
        .eq("date", today)
        .maybeSingle();

      if (cached?.brief && cached.input_hash === inputHash) {
        return json({ brief: cached.brief, cached: true, model: MODEL });
      }
    }

    const apiKey = Deno.env.get("ANTHROPIC_API_KEY");
    if (!apiKey) return json({ error: "missing_anthropic_key" }, 500);

    const response = await fetch("https://api.anthropic.com/v1/messages", {
      method: "POST",
      headers: {
        "x-api-key": apiKey,
        "anthropic-version": "2023-06-01",
        "content-type": "application/json",
      },
      body: JSON.stringify({
        model: MODEL,
        max_tokens: 360,
        system:
          "You are WolfMaster, a terse personal chief-of-staff. Write a 2-4 sentence command brief for the operator's day. Be specific and grounded only in the data provided. Never invent names, tasks, numbers, or events. Lead with what matters most. Optionally end with one sharp suggestion. No greeting, no markdown.",
        messages: [{ role: "user", content: buildPrompt(digest) }],
      }),
    });

    if (!response.ok) {
      return json({ error: "claude_failed", detail: await response.text() }, 502);
    }

    const data = await response.json();
    const brief = String(data?.content?.[0]?.text || "").trim();
    if (!brief) return json({ error: "empty_brief" }, 502);

    await supabase.from("ai_briefs").upsert({
      user_id: user.id,
      date: today,
      input_hash: inputHash,
      brief,
    });

    return json({ brief, cached: false, model: MODEL });
  } catch (error) {
    return json({ error: String(error?.message || error) }, 500);
  }
});

function json(body: unknown, status = 200) {
  return new Response(JSON.stringify(body), {
    status,
    headers: { ...cors, "content-type": "application/json" },
  });
}

async function sha256(value: string) {
  const hash = await crypto.subtle.digest("SHA-256", new TextEncoder().encode(value));
  return [...new Uint8Array(hash)].map((byte) => byte.toString(16).padStart(2, "0")).join("");
}

function buildPrompt(digest: any) {
  return [
    `Today: ${digest.today || new Date().toDateString()}`,
    `Daily Top 3: ${formatList(digest.top3)}`,
    `Weekly Top 5: ${formatList(digest.weekly)}`,
    `Recommended next action: ${digest.recommendation || "none"}`,
    `Priority signals: ${formatList(digest.signals)}`,
    `Attention required: ${formatList(digest.attention)}`,
    `People and family: ${formatList(digest.people)}`,
    `Calendar: ${formatList(digest.events)}`,
    `Momentum: ${digest.momentum ?? "n/a"}`,
    `Recent reflection: ${digest.reflection || "none"}`,
  ].join("\n");
}

function formatList(items: any) {
  if (!Array.isArray(items) || !items.length) return "none";
  return items
    .slice(0, 8)
    .map((item) => {
      if (typeof item === "string") return `- ${item}`;
      return `- ${item.text || item.title || item.name || item.label || JSON.stringify(item)}`;
    })
    .join("\n");
}
