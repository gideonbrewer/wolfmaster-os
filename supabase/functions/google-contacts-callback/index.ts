import "jsr:@supabase/functions-js/edge-runtime.d.ts";
import { createClient } from "jsr:@supabase/supabase-js@2";

Deno.serve(async (req) => {
  const url = new URL(req.url);
  const code = url.searchParams.get("code");
  const state = url.searchParams.get("state");
  const error = url.searchParams.get("error");

  const fail = (appUrl = Deno.env.get("APP_URL") || "https://wolfmaster.vercel.app/", detail = "connect_failed") =>
    Response.redirect(withParam(appUrl, "google_contacts", detail), 302);

  if (error) return fail(undefined, error);
  if (!code || !state) return fail(undefined, "missing_code");

  const secret = Deno.env.get("GOOGLE_STATE_SECRET");
  const clientId = Deno.env.get("GOOGLE_CLIENT_ID");
  const clientSecret = Deno.env.get("GOOGLE_CLIENT_SECRET");
  const serviceKey = Deno.env.get("SUPABASE_SERVICE_ROLE_KEY");
  if (!secret || !clientId || !clientSecret || !serviceKey) return fail(undefined, "missing_config");

  const parsed = await verifyState(state, secret).catch(() => null);
  if (!parsed?.uid) return fail(undefined, "bad_state");
  if (Date.now() - Number(parsed.ts || 0) > 10 * 60 * 1000) return fail(parsed.appUrl, "expired_state");

  const tokenRes = await fetch("https://oauth2.googleapis.com/token", {
    method: "POST",
    headers: { "content-type": "application/x-www-form-urlencoded" },
    body: new URLSearchParams({
      code,
      client_id: clientId,
      client_secret: clientSecret,
      redirect_uri: contactsRedirectUri(),
      grant_type: "authorization_code",
    }),
  });
  const token = await tokenRes.json();
  if (!tokenRes.ok || token.error) return fail(parsed.appUrl, token.error || "token_exchange_failed");

  const email = await fetchGoogleEmail(token.access_token).catch(() => parsed.accountHint || "");
  const admin = createClient(Deno.env.get("SUPABASE_URL")!, serviceKey);
  const expiresAt = token.expires_in ? new Date(Date.now() + Number(token.expires_in) * 1000).toISOString() : null;
  const { error: saveError } = await admin.from("google_contacts_tokens").upsert({
    user_id: parsed.uid,
    provider: "contacts",
    email,
    access_token: token.access_token,
    refresh_token: token.refresh_token || null,
    scope: token.scope || "",
    token_type: token.token_type || "Bearer",
    expires_at: expiresAt,
    updated_at: new Date().toISOString(),
  });
  if (saveError) return fail(parsed.appUrl, "save_failed");

  return Response.redirect(withParam(parsed.appUrl, "google_contacts", "connected"), 302);
});

function contactsRedirectUri() {
  return Deno.env.get("GOOGLE_CONTACTS_REDIRECT_URI") ||
    `${Deno.env.get("SUPABASE_URL")}/functions/v1/google-contacts-callback`;
}

async function fetchGoogleEmail(accessToken: string) {
  const res = await fetch("https://openidconnect.googleapis.com/v1/userinfo", {
    headers: { Authorization: `Bearer ${accessToken}` },
  });
  const data = await res.json();
  if (!res.ok || data.error) throw new Error(data.error?.message || data.error || "userinfo_failed");
  return data.email || "";
}

function withParam(appUrl: string, key: string, value: string) {
  const url = new URL(appUrl);
  url.searchParams.set(key, value);
  return url.toString();
}

async function verifyState(state: string, secret: string) {
  const [body, sig] = state.split(".");
  if (!body || !sig) throw new Error("bad_state");
  const key = await crypto.subtle.importKey("raw", new TextEncoder().encode(secret), { name: "HMAC", hash: "SHA-256" }, false, ["sign"]);
  const expectedRaw = await crypto.subtle.sign("HMAC", key, new TextEncoder().encode(body));
  const expected = [...new Uint8Array(expectedRaw)].map((b) => b.toString(16).padStart(2, "0")).join("");
  if (expected !== sig) throw new Error("bad_signature");
  return JSON.parse(atob(body));
}
