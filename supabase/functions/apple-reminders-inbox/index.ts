import "jsr:@supabase/functions-js/edge-runtime.d.ts";
import { createClient } from "jsr:@supabase/supabase-js@2";

const corsHeaders = {
  "Access-Control-Allow-Origin": "*",
  "Access-Control-Allow-Headers":
    "authorization, x-client-info, apikey, content-type, x-wm-capture-token",
  "Access-Control-Allow-Methods": "POST, OPTIONS",
};

function json(body: Record<string, unknown>, status = 200) {
  return new Response(JSON.stringify(body), {
    status,
    headers: { ...corsHeaders, "Content-Type": "application/json" },
  });
}

function clean(value: unknown) {
  return String(value ?? "").trim();
}

function cleanDate(value: unknown) {
  const raw = clean(value);
  if (!raw) return "";
  if (/^\d{4}-\d{2}-\d{2}$/.test(raw)) return raw;
  const parsed = new Date(raw);
  if (Number.isNaN(parsed.getTime())) return "";
  return parsed.toISOString().slice(0, 10);
}

async function stableId(input: string) {
  const data = new TextEncoder().encode(input);
  const hash = await crypto.subtle.digest("SHA-256", data);
  return Array.from(new Uint8Array(hash))
    .map((b) => b.toString(16).padStart(2, "0"))
    .join("")
    .slice(0, 40);
}

function shouldSkip(body: Record<string, unknown>) {
  const title = clean(body.title).toLowerCase();
  const notes = clean(body.notes).toLowerCase();
  const list = clean(body.list || body.listName || "WolfMaster Inbox").toLowerCase();
  if (list !== "wolfmaster inbox") return "wrong_list";
  if (body.completed === true || body.isCompleted === true) return "completed";
  if (/\b(grocery|groceries|shopping list|costco|meijer|target run)\b/.test(`${title} ${notes}`)) {
    return "excluded_capture";
  }
  return "";
}

async function requireUser(req: Request) {
  const authHeader = req.headers.get("Authorization") || "";
  const supabase = createClient(
    Deno.env.get("SUPABASE_URL")!,
    Deno.env.get("SUPABASE_ANON_KEY")!,
    { global: { headers: { Authorization: authHeader } } },
  );
  const { data, error } = await supabase.auth.getUser();
  if (error || !data.user) throw new Error("unauthorized");
  return data.user;
}

Deno.serve(async (req) => {
  if (req.method === "OPTIONS") return json({ ok: true });
  if (req.method !== "POST") return json({ error: "method_not_allowed" }, 405);

  let body: Record<string, unknown> = {};
  try {
    body = await req.json();
  } catch {
    return json({ error: "invalid_json" }, 400);
  }

  const serviceKey = Deno.env.get("SUPABASE_SERVICE_ROLE_KEY");
  if (!serviceKey) return json({ error: "missing_service_role_key" }, 500);
  const admin = createClient(Deno.env.get("SUPABASE_URL")!, serviceKey);
  const action = clean(body.action || "capture").toLowerCase();

  try {
    if (action === "capture") {
      const expected = Deno.env.get("WM_APPLE_REMINDERS_TOKEN") || "";
      let userId = Deno.env.get("WM_APPLE_REMINDERS_USER_ID") || "";
      const userEmail = clean(Deno.env.get("WM_APPLE_REMINDERS_USER_EMAIL")).toLowerCase();
      const token = req.headers.get("x-wm-capture-token") || clean(body.token);
      if (!expected || (!userId && !userEmail)) return json({ error: "missing_apple_reminders_config" }, 500);
      if (token !== expected) return json({ error: "unauthorized" }, 401);

      if (!userId && userEmail) {
        const userLookup = await admin.auth.admin.listUsers();
        if (userLookup.error) return json({ error: "user_lookup_failed", detail: userLookup.error.message }, 500);
        const matched = userLookup.data.users.find((user) => user.email?.toLowerCase() === userEmail);
        userId = matched?.id || userLookup.data.users[0]?.id || "";
        if (!userId) return json({ error: "apple_reminders_user_not_found" }, 500);
      }

      const skipReason = shouldSkip(body);
      if (skipReason) return json({ ok: true, skipped: true, reason: skipReason });

      const title = clean(body.title);
      if (!title) return json({ error: "missing_title" }, 400);
      const notes = clean(body.notes);
      const dueDate = cleanDate(body.dueDate || body.due_date);
      const sourceUrl = clean(body.url || body.sourceUrl || body.link);
      const sourceId =
        clean(body.sourceId || body.id || body.reminderId) ||
        (await stableId([title, notes, dueDate, sourceUrl].join("|")));

      const existing = await admin
        .from("apple_reminder_captures")
        .select("id,status")
        .eq("user_id", userId)
        .eq("source_system", "apple_reminders")
        .eq("source_id", sourceId)
        .maybeSingle();

      if (existing.error) return json({ error: "lookup_failed", detail: existing.error.message }, 500);
      if (existing.data?.status === "imported") {
        return json({ ok: true, duplicate: true, alreadyImported: true, id: existing.data.id });
      }

      const row = {
        user_id: userId,
        source_system: "apple_reminders",
        source_id: sourceId,
        list_name: "WolfMaster Inbox",
        title,
        notes: notes || null,
        due_date: dueDate || null,
        source_url: sourceUrl || null,
        status: "pending",
        payload: body,
        updated_at: new Date().toISOString(),
      };

      const result = existing.data
        ? await admin.from("apple_reminder_captures").update(row).eq("id", existing.data.id).select("id,status").single()
        : await admin.from("apple_reminder_captures").insert(row).select("id,status").single();

      if (result.error) return json({ error: "capture_failed", detail: result.error.message }, 500);
      return json({ ok: true, id: result.data.id, status: result.data.status, sourceId });
    }

    const user = await requireUser(req);

    if (action === "pending") {
      const expected = Deno.env.get("WM_APPLE_REMINDERS_TOKEN") || "";
      const userEmail = clean(Deno.env.get("WM_APPLE_REMINDERS_USER_EMAIL")).toLowerCase();
      if (expected && userEmail && user.email?.toLowerCase() === userEmail) {
        const claim = await admin
          .from("apple_reminder_captures")
          .update({ user_id: user.id, updated_at: new Date().toISOString() })
          .eq("source_system", "apple_reminders")
          .eq("status", "pending")
          .filter("payload->>token", "eq", expected);
        if (claim.error) return json({ error: "pending_claim_failed", detail: claim.error.message }, 500);
      }

      const { data, error } = await admin
        .from("apple_reminder_captures")
        .select("id,source_system,source_id,title,notes,due_date,source_url,payload,captured_at")
        .eq("user_id", user.id)
        .eq("status", "pending")
        .order("captured_at", { ascending: true })
        .limit(100);
      if (error) return json({ error: "pending_failed", detail: error.message }, 500);
      return json({ ok: true, items: data || [], count: data?.length || 0 });
    }

    if (action === "ack") {
      const ids = Array.isArray(body.ids) ? body.ids.map(clean).filter(Boolean) : [];
      if (!ids.length) return json({ ok: true, count: 0 });
      const { data, error } = await admin
        .from("apple_reminder_captures")
        .update({ status: "imported", imported_at: new Date().toISOString(), updated_at: new Date().toISOString() })
        .eq("user_id", user.id)
        .in("id", ids)
        .select("id");
      if (error) return json({ error: "ack_failed", detail: error.message }, 500);
      return json({ ok: true, count: data?.length || 0 });
    }

    return json({ error: "unknown_action" }, 400);
  } catch (error) {
    const message = error instanceof Error ? error.message : "unexpected_error";
    return json({ error: message === "unauthorized" ? "unauthorized" : "unexpected_error", detail: message }, message === "unauthorized" ? 401 : 500);
  }
});
