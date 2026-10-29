-- REVIEW ONLY. Never apply to a remote project without approval for this exact file.
-- Additive: creates only finance_snapshots, its policies/index/trigger/function.
-- No legacy-table/auth-setting/token changes and no existing-data migration.
begin;

create table public.finance_snapshots (
  id uuid primary key default gen_random_uuid(),
  user_id uuid not null default auth.uid() references auth.users(id) on delete cascade,
  kind text not null check (kind in ('earnings','worth')),
  as_of_date date not null check (as_of_date between date '1900-01-01' and current_date),
  currency text not null check (currency in ('USD','EUR','GBP','CAD')),
  coverage text not null check (char_length(btrim(coverage)) between 1 and 500),
  source text not null default 'manual' check (source = 'manual'),
  schema_version integer not null default 1 check (schema_version = 1),
  work numeric(15,2),
  consulting numeric(15,2),
  mining_revenue numeric(15,2),
  mining_expenses numeric(15,2),
  realized numeric(15,2),
  unrealized numeric(15,2),
  assets numeric(15,2),
  liabilities numeric(15,2),
  revision bigint not null default 1 check (revision >= 1),
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  constraint finance_snapshots_unique_period unique (user_id, kind, as_of_date, currency),
  constraint finance_snapshots_shape check (
    (kind = 'earnings' and assets is null and liabilities is null
      and num_nonnulls(work, consulting, mining_revenue, mining_expenses, realized, unrealized) > 0)
    or (kind = 'worth' and assets is not null and liabilities is not null
      and num_nonnulls(work, consulting, mining_revenue, mining_expenses, realized, unrealized) = 0)
  ),
  constraint finance_snapshots_finite_amounts check (
    (work is null or work between 0 and 9999999999999.99)
    and (consulting is null or consulting between -9999999999999.99 and 9999999999999.99)
    and (mining_revenue is null or mining_revenue between 0 and 9999999999999.99)
    and (mining_expenses is null or mining_expenses between 0 and 9999999999999.99)
    and (realized is null or realized between -9999999999999.99 and 9999999999999.99)
    and (unrealized is null or unrealized between -9999999999999.99 and 9999999999999.99)
    and (assets is null or assets between 0 and 9999999999999.99)
    and (liabilities is null or liabilities between 0 and 9999999999999.99)
  )
);

alter table public.finance_snapshots enable row level security;
alter table public.finance_snapshots force row level security;
-- Remove inherited broad defaults, including TRUNCATE which bypasses RLS.
revoke all on table public.finance_snapshots from public, anon, authenticated;
grant select, insert, update, delete on table public.finance_snapshots to authenticated;

create policy finance_owner_select on public.finance_snapshots
  for select to authenticated using ((select auth.uid()) = user_id);
create policy finance_owner_insert on public.finance_snapshots
  for insert to authenticated with check ((select auth.uid()) = user_id);
create policy finance_owner_update on public.finance_snapshots
  for update to authenticated using ((select auth.uid()) = user_id)
  with check ((select auth.uid()) = user_id);
create policy finance_owner_delete on public.finance_snapshots
  for delete to authenticated using ((select auth.uid()) = user_id);
-- Anonymous Supabase Auth users also receive the authenticated role. Deny them,
-- and deny missing/ambiguous claims. Never authorize using user_metadata.
create policy finance_permanent_user on public.finance_snapshots
  as restrictive for all to authenticated
  using ((select auth.uid()) is not null and ((select auth.jwt()) ->> 'is_anonymous') = 'false')
  with check ((select auth.uid()) is not null and ((select auth.jwt()) ->> 'is_anonymous') = 'false');

create function public.finance_snapshot_touch() returns trigger
language plpgsql security invoker set search_path = pg_catalog as $$
begin
  if new.id <> old.id then raise exception 'snapshot_id_immutable' using errcode = '23514'; end if;
  new.created_at := old.created_at;
  new.updated_at := clock_timestamp();
  new.revision := old.revision + 1;
  return new;
end;
$$;
revoke all on function public.finance_snapshot_touch() from public, anon, authenticated;
create trigger finance_snapshot_touch before update on public.finance_snapshots
  for each row execute function public.finance_snapshot_touch();

comment on table public.finance_snapshots is
  'Owner-only manual cumulative YTD or net-worth snapshots. Excluded from legacy snapshots, general backups, telemetry and AI briefs. No automatic imports.';
commit;
