create table if not exists calendar_connections (
  user_id uuid primary key references auth.users(id) on delete cascade,
  payload jsonb not null default '{}'::jsonb,
  updated_at timestamptz default now()
);

alter table calendar_connections enable row level security;

drop policy if exists "own calendar connection" on calendar_connections;
create policy "own calendar connection" on calendar_connections
  for all
  using (auth.uid() = user_id)
  with check (auth.uid() = user_id);

create table if not exists google_oauth_tokens (
  user_id uuid primary key references auth.users(id) on delete cascade,
  provider text not null default 'google',
  access_token text not null,
  refresh_token text,
  scope text,
  token_type text,
  expires_at timestamptz,
  updated_at timestamptz default now()
);

alter table google_oauth_tokens enable row level security;

-- Intentionally no user-facing policies. Edge Functions read/write this table
-- with the Supabase service role so Google refresh tokens never reach the app.

create table if not exists email_connections (
  user_id uuid primary key references auth.users(id) on delete cascade,
  payload jsonb not null default '{}'::jsonb,
  updated_at timestamptz default now()
);

alter table email_connections enable row level security;

drop policy if exists "own email connection" on email_connections;
create policy "own email connection" on email_connections
  for all
  using (auth.uid() = user_id)
  with check (auth.uid() = user_id);

create table if not exists google_gmail_tokens (
  user_id uuid primary key references auth.users(id) on delete cascade,
  provider text not null default 'gmail',
  email text,
  access_token text not null,
  refresh_token text,
  scope text,
  token_type text,
  expires_at timestamptz,
  updated_at timestamptz default now()
);

alter table google_gmail_tokens enable row level security;

-- Intentionally no user-facing policies. Edge Functions read/write this table
-- with the Supabase service role so Gmail refresh tokens never reach the app.
