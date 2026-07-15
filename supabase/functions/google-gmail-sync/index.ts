import "jsr:@supabase/functions-js/edge-runtime.d.ts";
import { createClient } from "jsr:@supabase/supabase-js@2";

const cors = {
  "Access-Control-Allow-Origin": "*",
  "Access-Control-Allow-Headers": "authorization, apikey, content-type",
  "Access-Control-Allow-Methods": "POST, OPTIONS",
};

Deno.serve(async (req) => {
  if (req.method === "OPTIONS") return json({ ok: true });
  if (req.method !== "POST") return json({ error: "method_not_allowed" }, 405);

  const userClient = createClient(
    Deno.env.get("SUPABASE_URL")!,
    Deno.env.get("SUPABASE_ANON_KEY")!,
    { global: { headers: { Authorization: req.headers.get("Authorization") || "" } } },
  );
  const { data: { user }, error: userError } = await userClient.auth.getUser();
  if (userError || !user) return json({ error: "unauthorized" }, 401);

  const serviceKey = Deno.env.get("SUPABASE_SERVICE_ROLE_KEY");
  if (!serviceKey) return json({ error: "missing_service_role_key" }, 500);
  const admin = createClient(Deno.env.get("SUPABASE_URL")!, serviceKey);
  const { data: tokenRow, error: tokenError } = await admin
    .from("google_gmail_tokens")
    .select("*")
    .eq("user_id", user.id)
    .maybeSingle();
  if (tokenError) return json({ error: "token_load_failed", detail: tokenError.message }, 500);
  if (!tokenRow?.access_token) return json({ error: "gmail_not_connected" }, 409);

  let accessToken = tokenRow.access_token;
  const expiresAt = tokenRow.expires_at ? new Date(tokenRow.expires_at).getTime() : 0;
  if (expiresAt && expiresAt < Date.now() + 90_000) {
    if (!tokenRow.refresh_token) return json({ error: "missing_refresh_token" }, 409);
    const refreshed = await refreshToken(tokenRow.refresh_token);
    accessToken = refreshed.access_token;
    await admin.from("google_gmail_tokens").update({
      access_token: refreshed.access_token,
      expires_at: refreshed.expires_in ? new Date(Date.now() + Number(refreshed.expires_in) * 1000).toISOString() : tokenRow.expires_at,
      scope: refreshed.scope || tokenRow.scope,
      token_type: refreshed.token_type || tokenRow.token_type,
      updated_at: new Date().toISOString(),
    }).eq("user_id", user.id);
  }

  const listParams = new URLSearchParams({
    maxResults: "15",
    q: "newer_than:30d -category:promotions -category:social",
  });
  const listRes = await fetch(`https://gmail.googleapis.com/gmail/v1/users/me/messages?${listParams.toString()}`, {
    headers: { Authorization: `Bearer ${accessToken}` },
  });
  const listData = await listRes.json();
  if (!listRes.ok || listData.error) {
    return json({ error: "gmail_list_failed", detail: listData.error?.message || listData.error || "Gmail list request failed" }, 502);
  }

  const messages = await Promise.all((listData.messages || []).slice(0, 15).map((m: any) => fetchMessage(accessToken, m.id)));
  const items = messages.filter(Boolean).map(normalizeMessage).filter(Boolean);
  const unread = items.filter((m: any) => m.unread).length;
  const needsReply = items.filter((m: any) => m.needsReply).length;
  const waitingOn = items.filter((m: any) => m.waitingOn).length;

  return json({
    account: tokenRow.email || "",
    items,
    unread,
    needsReply,
    waitingOn,
    syncedAt: new Date().toISOString(),
    count: items.length,
  });
});

async function fetchMessage(accessToken: string, id: string) {
  const params = new URLSearchParams({ format: "metadata" });
  ["From", "Subject", "Date", "To"].forEach((h) => params.append("metadataHeaders", h));
  const res = await fetch(`https://gmail.googleapis.com/gmail/v1/users/me/messages/${id}?${params.toString()}`, {
    headers: { Authorization: `Bearer ${accessToken}` },
  });
  const data = await res.json();
  if (!res.ok || data.error) return null;
  return data;
}

async function refreshToken(refreshToken: string) {
  const res = await fetch("https://oauth2.googleapis.com/token", {
    method: "POST",
    headers: { "content-type": "application/x-www-form-urlencoded" },
    body: new URLSearchParams({
      refresh_token: refreshToken,
      client_id: Deno.env.get("GOOGLE_CLIENT_ID") || "",
      client_secret: Deno.env.get("GOOGLE_CLIENT_SECRET") || "",
      grant_type: "refresh_token",
    }),
  });
  const data = await res.json();
  if (!res.ok || data.error) throw new Error(data.error_description || data.error || "refresh_failed");
  return data;
}

function normalizeMessage(item: any) {
  const headers = new Map((item.payload?.headers || []).map((h: any) => [String(h.name || "").toLowerCase(), h.value || ""]));
  const subject = String(headers.get("subject") || "(No subject)");
  const fromRaw = String(headers.get("from") || "");
  const dateRaw = String(headers.get("date") || "");
  const snippet = String(item.snippet || "");
  const labels = item.labelIds || [];
  const unread = labels.includes("UNREAD");
  const sentByMe = labels.includes("SENT");
  const from = parseFrom(fromRaw);
  const text = `${subject} ${snippet}`.toLowerCase();
  const needsReply = unread && !sentByMe && /question|thoughts|can you|could you|please|need|confirm|follow up|following up|available|meeting|call|reply|response/.test(text);
  const waitingOn = sentByMe || /waiting|follow up|following up|checking in|circling back/.test(text);
  const priority = needsReply ? "Needs reply" : waitingOn ? "Waiting on" : unread ? "Unread" : "FYI";
  return {
    id: item.id,
    threadId: item.threadId,
    subject,
    fromName: from.name,
    fromEmail: from.email,
    date: safeDate(dateRaw),
    snippet,
    unread,
    needsReply,
    waitingOn,
    priority,
  };
}

function parseFrom(raw: string) {
  const match = raw.match(/^(.*?)<([^>]+)>$/);
  if (!match) return { name: raw.replace(/"/g, "").trim() || "Unknown", email: raw.includes("@") ? raw.trim() : "" };
  return { name: match[1].replace(/"/g, "").trim() || match[2], email: match[2].trim() };
}

function safeDate(raw: string) {
  const d = new Date(raw);
  return Number.isFinite(d.getTime()) ? d.toISOString() : "";
}

function json(body: unknown, status = 200) {
  return new Response(JSON.stringify(body), { status, headers: { ...cors, "content-type": "application/json" } });
}
