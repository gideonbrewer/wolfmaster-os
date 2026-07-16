import "jsr:@supabase/functions-js/edge-runtime.d.ts";
import { createClient } from "jsr:@supabase/supabase-js@2";

const cors = {
  "Access-Control-Allow-Origin": "*",
  "Access-Control-Allow-Headers": "authorization, apikey, content-type",
  "Access-Control-Allow-Methods": "POST, OPTIONS",
};

const SCOPES = [
  "openid",
  "email",
  "profile",
  "https://www.googleapis.com/auth/contacts.readonly",
];

Deno.serve(async (req) => {
  if (req.method === "OPTIONS") return json({ ok: true });
  if (req.method !== "POST") return json({ error: "method_not_allowed" }, 405);

  const supabase = createClient(
    Deno.env.get("SUPABASE_URL")!,
    Deno.env.get("SUPABASE_ANON_KEY")!,
    { global: { headers: { Authorization: req.headers.get("Authorization") || "" } } },
  );
  const { data: { user }, error } = await supabase.auth.getUser();
  if (error || !user) return json({ error: "unauthorized" }, 401);

  const clientId = Deno.env.get("GOOGLE_CLIENT_ID");
  const redirectUri = contactsRedirectUri();
  const secret = Deno.env.get("GOOGLE_STATE_SECRET");
  if (!clientId || !redirectUri || !secret) return json({ error: "missing_google_oauth_config" }, 500);

  const { appUrl = "", accountHint = "" } = await req.json().catch(() => ({}));
  const fallbackUrl = Deno.env.get("APP_URL") || "https://wolfmaster.vercel.app/";
  const statePayload = {
    uid: user.id,
    appUrl: safeAppUrl(appUrl) || fallbackUrl,
    accountHint: String(accountHint || ""),
    ts: Date.now(),
    nonce: crypto.randomUUID(),
  };
  const state = await signState(statePayload, secret);
  const params = new URLSearchParams({
    client_id: clientId,
    redirect_uri: redirectUri,
    response_type: "code",
    scope: SCOPES.join(" "),
    access_type: "offline",
    prompt: "consent",
    include_granted_scopes: "true",
    state,
  });
  if (accountHint) params.set("login_hint", String(accountHint));

  return json({ authUrl: `https://accounts.google.com/o/oauth2/v2/auth?${params.toString()}` });
});

function contactsRedirectUri() {
  return Deno.env.get("GOOGLE_CONTACTS_REDIRECT_URI") ||
    `${Deno.env.get("SUPABASE_URL")}/functions/v1/google-contacts-callback`;
}

function safeAppUrl(value: string) {
  try {
    const url = new URL(String(value || ""));
    if (!["http:", "https:"].includes(url.protocol)) return "";
    return url.toString();
  } catch {
    return "";
  }
}

async function signState(payload: unknown, secret: string) {
  const body = btoa(JSON.stringify(payload));
  const key = await crypto.subtle.importKey("raw", new TextEncoder().encode(secret), { name: "HMAC", hash: "SHA-256" }, false, ["sign"]);
  const sig = await crypto.subtle.sign("HMAC", key, new TextEncoder().encode(body));
  const hex = [...new Uint8Array(sig)].map((b) => b.toString(16).padStart(2, "0")).join("");
  return `${body}.${hex}`;
}

function json(body: unknown, status = 200) {
  return new Response(JSON.stringify(body), { status, headers: { ...cors, "content-type": "application/json" } });
}
