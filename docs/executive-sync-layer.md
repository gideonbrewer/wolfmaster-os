# Executive Sync Layer

WolfMaster is the executive attention layer, not the archive.

Canonical systems remain:

- TickTick for canonical tasks and habits
- Notion for durable project context, decisions, relationships, and knowledge
- Google Calendar for scheduled commitments
- Gmail for communication loops
- Apple Reminders for rapid capture when technically available
- ChatGPT for strategy, prioritization, drafting, and structured sync packets
- WolfMaster for daily attention, prioritization, briefings, and controlled write-back

## Phase 1

Open `Review -> Sync`.

You can paste a structured JSON sync packet and press `Import Sync Packet`, or press `Load Initial Packet` to seed the first executive packet.

The importer:

- Normalizes records into Unified Executive Items
- Uses `sourceSystem + sourceId` when present
- Falls back to a stable fingerprint from title, domain, type, project, and owner
- Updates matching items instead of duplicating them
- Creates missing items
- Sends canonical-system conflicts to a review queue
- Preserves an audit log
- Leaves completed or archived items out of the active dashboard while retaining them in history

## Adapter Contract

External integrations should normalize into the same model before merge:

```ts
interface SyncAdapter {
  pull(cursor?: string): Promise<SyncResult>;
  previewPush?(changes: ChangeSet): Promise<PushPreview>;
  push?(approvedChanges: ChangeSet): Promise<PushResult>;
}
```

Planned adapters (not connected):

- `TickTickAdapter` — canonical tasks; habit API coverage must be verified separately

- `NotionAdapter`
- `GoogleCalendarAdapter`
- `GmailAdapter`
- `RemindersAdapter`
- `ChatGPTSyncPacketAdapter`

All write-back requires explicit approval.

## Local Validation

```bash
node tests/executive-sync.test.mjs
```

The app is still a single-file React/Babel build, so JSX validation can be run with the existing parser command used during development.

The companion preview adds a gated canonical completion/read-back contract in `assets/companion/model.js`; no live adapter is enabled. See [the current implementation handoff](companion-first-version.md).
