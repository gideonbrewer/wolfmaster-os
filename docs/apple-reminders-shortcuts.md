# Apple Reminders Capture Bridge

WolfMaster does not read Apple Reminders natively from the web app. iOS does not expose a direct Reminders API to a PWA.

Use this one-way flow instead:

`Siri / Apple Reminders -> WolfMaster Inbox list -> Apple Shortcut -> WolfMaster Inbox / Untriaged -> WolfMaster triage`

Do not use two-way sync. Apple Reminders is capture only; WolfMaster is the task system.

## Supabase Setup

Apply the database file:

```bash
npm exec --yes supabase -- db query --linked --file supabase/sql/apple_reminders.sql
```

Deploy the Edge Function:

```bash
npm exec --yes supabase -- functions deploy apple-reminders-inbox --no-verify-jwt --project-ref cgbyfooxstxinttfvwzq
```

Set these Supabase secrets:

```bash
npm exec --yes supabase -- secrets set WM_APPLE_REMINDERS_TOKEN='PRIVATE_RANDOM_TOKEN' --project-ref cgbyfooxstxinttfvwzq
npm exec --yes supabase -- secrets set WM_APPLE_REMINDERS_USER_ID='YOUR_SUPABASE_USER_ID' --project-ref cgbyfooxstxinttfvwzq
```

## iPhone Shortcut

Create one Apple Reminders list named:

```text
WolfMaster Inbox
```

Create a Shortcut named:

```text
Send WolfMaster Inbox
```

Shortcut steps:

1. Find Reminders
   - List is `WolfMaster Inbox`
   - Is Completed is false

2. Repeat with Each Reminder

3. Get Contents of URL
   - URL:

```text
https://cgbyfooxstxinttfvwzq.supabase.co/functions/v1/apple-reminders-inbox
```

   - Method: `POST`
   - Headers:

```text
apikey: sb_publishable_dG_9EvJgTLiw95ByLGEkrA_XJSG1tbj
content-type: application/json
x-wm-capture-token: PRIVATE_RANDOM_TOKEN
```

   - Request Body: JSON

```json
{
  "action": "capture",
  "list": "WolfMaster Inbox",
  "sourceId": "Reminder Identifier",
  "title": "Reminder Title",
  "notes": "Reminder Notes",
  "dueDate": "Reminder Due Date",
  "url": "Reminder URL"
}
```

Use the matching Shortcut variables from the repeated Reminder for each value.

4. If the response is successful, mark the repeated Reminder as completed.

5. End Repeat.

## In WolfMaster

Open PLAN and tap the small check icon in the top action row.

WolfMaster will:

- Pull pending Apple captures.
- Create missing tasks under `Task Queue -> Inbox`.
- Skip duplicates.
- Mark successfully pulled captures as imported.

Triage inside WolfMaster after import. Assign project, priority, due date, tags, and whether it belongs in Daily 3 or Weekly 5.
