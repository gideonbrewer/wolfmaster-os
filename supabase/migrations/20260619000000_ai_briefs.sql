-- AI Command Brief cache: at most one generated brief per user per day.
-- The Edge Function (ai-brief) reads/writes this; RLS keeps each user to their own rows.

create table if not exists ai_briefs (
  user_id uuid not null references auth.users(id) on delete cascade,
  date date not null,
  input_hash text not null,
  brief text not null,
  created_at timestamptz default now(),
  primary key (user_id, date)
);

alter table ai_briefs enable row level security;

drop policy if exists "own briefs" on ai_briefs;
create policy "own briefs" on ai_briefs
  for all using (auth.uid() = user_id) with check (auth.uid() = user_id);
