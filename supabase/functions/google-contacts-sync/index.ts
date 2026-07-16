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
    .from("google_contacts_tokens")
    .select("*")
    .eq("user_id", user.id)
    .maybeSingle();
  if (tokenError) return json({ error: "token_load_failed", detail: tokenError.message }, 500);
  if (!tokenRow?.access_token) return json({ error: "contacts_not_connected" }, 409);

  let accessToken = tokenRow.access_token;
  const expiresAt = tokenRow.expires_at ? new Date(tokenRow.expires_at).getTime() : 0;
  if (expiresAt && expiresAt < Date.now() + 90_000) {
    if (!tokenRow.refresh_token) return json({ error: "missing_refresh_token" }, 409);
    const refreshed = await refreshToken(tokenRow.refresh_token);
    accessToken = refreshed.access_token;
    await admin.from("google_contacts_tokens").update({
      access_token: refreshed.access_token,
      expires_at: refreshed.expires_in ? new Date(Date.now() + Number(refreshed.expires_in) * 1000).toISOString() : tokenRow.expires_at,
      scope: refreshed.scope || tokenRow.scope,
      token_type: refreshed.token_type || tokenRow.token_type,
      updated_at: new Date().toISOString(),
    }).eq("user_id", user.id);
  }

  const params = new URLSearchParams({
    pageSize: "200",
    personFields: "names,emailAddresses,phoneNumbers,organizations,photos",
    sortOrder: "FIRST_NAME_ASCENDING",
  });
  const res = await fetch(`https://people.googleapis.com/v1/people/me/connections?${params.toString()}`, {
    headers: { Authorization: `Bearer ${accessToken}` },
  });
  const data = await res.json();
  if (!res.ok || data.error) {
    return json({ error: "contacts_sync_failed", detail: data.error?.message || data.error || "Contacts request failed" }, 502);
  }

  const contacts = (data.connections || []).map(normalizeContact).filter((x: any) => x.name && (x.email || x.phone));
  return json({
    account: tokenRow.email || "",
    contacts,
    count: contacts.length,
    syncedAt: new Date().toISOString(),
  });
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

function normalizeContact(person: any) {
  const name = person.names?.find((n: any) => n.displayName)?.displayName || "";
  const email = person.emailAddresses?.find((e: any) => e.value)?.value || "";
  const phone = person.phoneNumbers?.find((p: any) => p.value)?.value || "";
  const org = person.organizations?.find((o: any) => o.name || o.title) || {};
  const photo = person.photos?.find((p: any) => p.url && !p.default)?.url || "";
  return {
    id: person.resourceName || crypto.randomUUID(),
    name: String(name).trim(),
    email: String(email).trim(),
    phone: String(phone).trim(),
    organization: String(org.name || "").trim(),
    role: String(org.title || "").trim(),
    photo: String(photo || "").trim(),
    source: "google_contacts",
  };
}

function json(body: unknown, status = 200) {
  return new Response(JSON.stringify(body), { status, headers: { ...cors, "content-type": "application/json" } });
}
