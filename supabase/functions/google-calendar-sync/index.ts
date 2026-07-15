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
    .from("google_oauth_tokens")
    .select("*")
    .eq("user_id", user.id)
    .maybeSingle();
  if (tokenError) return json({ error: "token_load_failed", detail: tokenError.message }, 500);
  if (!tokenRow?.access_token) return json({ error: "google_not_connected" }, 409);

  let accessToken = tokenRow.access_token;
  const expiresAt = tokenRow.expires_at ? new Date(tokenRow.expires_at).getTime() : 0;
  if (expiresAt && expiresAt < Date.now() + 90_000) {
    if (!tokenRow.refresh_token) return json({ error: "missing_refresh_token" }, 409);
    const refreshed = await refreshToken(tokenRow.refresh_token);
    accessToken = refreshed.access_token;
    await admin.from("google_oauth_tokens").update({
      access_token: refreshed.access_token,
      expires_at: refreshed.expires_in ? new Date(Date.now() + Number(refreshed.expires_in) * 1000).toISOString() : tokenRow.expires_at,
      scope: refreshed.scope || tokenRow.scope,
      token_type: refreshed.token_type || tokenRow.token_type,
      updated_at: new Date().toISOString(),
    }).eq("user_id", user.id);
  }

  const now = new Date();
  const timeMin = new Date(now.getTime() - 12 * 60 * 60 * 1000).toISOString();
  const timeMax = new Date(now.getTime() + 30 * 24 * 60 * 60 * 1000).toISOString();
  const params = new URLSearchParams({
    timeMin,
    timeMax,
    singleEvents: "true",
    orderBy: "startTime",
    maxResults: "100",
  });
  const calendarRes = await fetch(`https://www.googleapis.com/calendar/v3/calendars/primary/events?${params.toString()}`, {
    headers: { Authorization: `Bearer ${accessToken}` },
  });
  const calendarData = await calendarRes.json();
  if (!calendarRes.ok || calendarData.error) {
    return json({ error: "google_calendar_failed", detail: calendarData.error?.message || calendarData.error || "Calendar request failed" }, 502);
  }

  const events = (calendarData.items || [])
    .filter((item: any) => item.status !== "cancelled")
    .map(normalizeEvent)
    .filter(Boolean);

  return json({ events, syncedAt: new Date().toISOString(), count: events.length });
});

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

function normalizeEvent(item: any) {
  const startValue = item.start?.dateTime || item.start?.date;
  const endValue = item.end?.dateTime || item.end?.date;
  if (!startValue) return null;
  const allDay = !!item.start?.date;
  const start = new Date(startValue);
  const end = endValue ? new Date(endValue) : null;
  const zone = item.start?.timeZone || item.end?.timeZone || "America/Detroit";
  const local = allDay ? null : localDateTimeParts(start, zone);
  const date = allDay ? String(startValue).slice(0, 10) : local.date;
  const time = allDay ? "All day" : local.time;
  const minutes = end && !allDay ? Math.max(15, Math.round((end.getTime() - start.getTime()) / 60000)) : "";
  return {
    id: item.id,
    date,
    time,
    timeZone: zone,
    startsAt: allDay ? "" : start.toISOString(),
    title: item.summary || "Calendar item",
    note: minutes ? `${minutes}m` : "",
    source: "google",
    htmlLink: item.htmlLink || "",
  };
}

function localDateTimeParts(date: Date, timeZone: string) {
  const parts = new Intl.DateTimeFormat("en-US", {
    timeZone,
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
    hour12: false,
  }).formatToParts(date).reduce((acc: Record<string, string>, part) => {
    if (part.type !== "literal") acc[part.type] = part.value;
    return acc;
  }, {});
  const hour = parts.hour === "24" ? "00" : parts.hour;
  return {
    date: `${parts.year}-${parts.month}-${parts.day}`,
    time: `${hour}:${parts.minute}`,
  };
}

function json(body: unknown, status = 200) {
  return new Response(JSON.stringify(body), { status, headers: { ...cors, "content-type": "application/json" } });
}
