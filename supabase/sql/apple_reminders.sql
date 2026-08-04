create table if not exists public.apple_reminder_captures (
  id uuid primary key default gen_random_uuid(),
  user_id uuid not null references auth.users(id) on delete cascade,
  source_system text not null default 'apple_reminders',
  source_id text not null,
  list_name text not null default 'WolfMaster Inbox',
  title text not null,
  notes text,
  due_date date,
  source_url text,
  status text not null default 'pending' check (status in ('pending', 'imported', 'skipped')),
  payload jsonb not null default '{}'::jsonb,
  captured_at timestamptz not null default now(),
  imported_at timestamptz,
  updated_at timestamptz not null default now(),
  unique (user_id, source_system, source_id)
);

alter table public.apple_reminder_captures enable row level security;

create policy "apple reminder captures are user readable"
  on public.apple_reminder_captures
  for select
  using (auth.uid() = user_id);

create policy "apple reminder captures are user updateable"
  on public.apple_reminder_captures
  for update
  using (auth.uid() = user_id)
  with check (auth.uid() = user_id);

create index if not exists apple_reminder_captures_user_status_idx
  on public.apple_reminder_captures(user_id, status, captured_at desc);
