create schema if not exists private;

create type public.member_role as enum ('elder', 'family');
create type public.report_status as enum ('draft', 'confirmed', 'discarded');

create or replace function private.touch_updated_at()
returns trigger
language plpgsql
set search_path = ''
as $$
begin
  new.updated_at := now();
  return new;
end;
$$;

create table public.families (
  id uuid primary key default gen_random_uuid(),
  line_group_id text unique,
  display_name text,
  patient_nickname text not null default '長輩',
  dry_weight_kg numeric(5, 2) check (dry_weight_kg between 20 and 200),
  daily_water_limit_ml integer not null default 1000 check (daily_water_limit_ml between 200 and 4000),
  metric_overrides jsonb not null default '{}'::jsonb,
  sheet_id text,
  disclaimer_accepted_at timestamptz,
  disclaimer_accepted_by uuid,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create table public.users (
  id uuid primary key default gen_random_uuid(),
  line_user_id text not null unique,
  display_name text,
  active_family_id uuid references public.families (id) on delete set null,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

alter table public.families
  add constraint families_disclaimer_by_fkey
  foreign key (disclaimer_accepted_by) references public.users (id) on delete set null;

create table public.family_members (
  family_id uuid not null references public.families (id) on delete cascade,
  user_id uuid not null references public.users (id) on delete cascade,
  role public.member_role not null default 'family',
  notify_alerts boolean not null default true,
  created_at timestamptz not null default now(),
  primary key (family_id, user_id)
);
create index family_members_user_idx on public.family_members (user_id);

create table public.medical_reports (
  id uuid primary key default gen_random_uuid(),
  family_id uuid not null references public.families (id) on delete cascade,
  test_date date not null,
  report_month date generated always as ((date_trunc('month', test_date::timestamp))::date) stored,
  potassium numeric(5, 2),
  phosphorus numeric(5, 2),
  calcium numeric(5, 2),
  hemoglobin numeric(5, 2),
  sodium numeric(6, 2),
  albumin numeric(4, 2),
  bun numeric(6, 1),
  creatinine numeric(5, 2),
  kt_v numeric(4, 2),
  ipth numeric(7, 1),
  extra jsonb not null default '{}'::jsonb,
  uncertain_fields text[] not null default '{}',
  status public.report_status not null default 'draft',
  source text not null default 'ocr' check (source in ('ocr', 'manual', 'sheets')),
  batch_id uuid,
  created_by uuid references public.users (id) on delete set null,
  confirmed_at timestamptz,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);
create unique index medical_reports_confirmed_uniq
  on public.medical_reports (family_id, test_date) where status = 'confirmed';
create index medical_reports_family_date_idx on public.medical_reports (family_id, test_date desc);
create index medical_reports_batch_idx on public.medical_reports (batch_id);

create table public.daily_records (
  id uuid primary key default gen_random_uuid(),
  family_id uuid not null references public.families (id) on delete cascade,
  record_date date not null,
  weight_kg numeric(5, 2) check (weight_kg between 20 and 200),
  systolic smallint check (systolic between 50 and 260),
  diastolic smallint check (diastolic between 30 and 160),
  pulse smallint check (pulse between 30 and 200),
  water_ml integer not null default 0 check (water_ml >= 0),
  note text,
  updated_by uuid references public.users (id) on delete set null,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  unique (family_id, record_date)
);

create table public.care_rules (
  id uuid primary key default gen_random_uuid(),
  family_id uuid references public.families (id) on delete cascade,
  metric text,
  direction text not null default 'any' check (direction in ('high', 'low', 'any')),
  min_level text not null default 'yellow' check (min_level in ('yellow', 'red')),
  title text not null,
  content text not null,
  priority integer not null default 100,
  is_active boolean not null default true,
  created_by uuid references public.users (id) on delete set null,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);
create index care_rules_lookup_idx on public.care_rules (family_id, metric) where is_active;

create table public.ai_advices (
  id uuid primary key default gen_random_uuid(),
  family_id uuid not null references public.families (id) on delete cascade,
  report_id uuid references public.medical_reports (id) on delete set null,
  text text not null,
  speech_text text not null,
  audio_path text,
  audio_duration_ms integer,
  created_at timestamptz not null default now()
);
create index ai_advices_family_idx on public.ai_advices (family_id, created_at desc);

create table public.reminders (
  id uuid primary key default gen_random_uuid(),
  family_id uuid not null references public.families (id) on delete cascade,
  kind text not null check (kind in ('weight', 'dialysis', 'clinic', 'water', 'custom')),
  message text not null,
  days_of_week smallint[] not null default '{1,2,3,4,5,6,7}',
  time_of_day time not null,
  is_active boolean not null default true,
  last_sent_on date,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  unique (family_id, kind)
);

create table public.conversation_states (
  line_user_id text not null,
  context_id text not null,
  state text not null,
  payload jsonb not null default '{}'::jsonb,
  expires_at timestamptz not null,
  primary key (line_user_id, context_id)
);

create table public.webhook_events (
  event_id text primary key,
  received_at timestamptz not null default now()
);

create trigger families_touch before update on public.families
  for each row execute function private.touch_updated_at();
create trigger users_touch before update on public.users
  for each row execute function private.touch_updated_at();
create trigger medical_reports_touch before update on public.medical_reports
  for each row execute function private.touch_updated_at();
create trigger daily_records_touch before update on public.daily_records
  for each row execute function private.touch_updated_at();
create trigger care_rules_touch before update on public.care_rules
  for each row execute function private.touch_updated_at();
create trigger reminders_touch before update on public.reminders
  for each row execute function private.touch_updated_at();

create or replace function public.add_water(
  p_family_id uuid,
  p_date date,
  p_ml integer,
  p_user_id uuid
)
returns integer
language plpgsql
set search_path = ''
as $$
declare
  v_total integer;
begin
  insert into public.daily_records (family_id, record_date, water_ml, updated_by)
  values (p_family_id, p_date, greatest(p_ml, 0), p_user_id)
  on conflict (family_id, record_date)
  do update set water_ml = greatest(public.daily_records.water_ml + p_ml, 0),
                updated_by = excluded.updated_by
  returning water_ml into v_total;
  return v_total;
end;
$$;
revoke execute on function public.add_water(uuid, date, integer, uuid) from public, anon, authenticated;
grant execute on function public.add_water(uuid, date, integer, uuid) to service_role;

alter table public.families enable row level security;
alter table public.users enable row level security;
alter table public.family_members enable row level security;
alter table public.medical_reports enable row level security;
alter table public.daily_records enable row level security;
alter table public.care_rules enable row level security;
alter table public.ai_advices enable row level security;
alter table public.reminders enable row level security;
alter table public.conversation_states enable row level security;
alter table public.webhook_events enable row level security;

create or replace function private.current_line_user_id()
returns text
language sql
stable
set search_path = ''
as $$
  select nullif(auth.jwt() ->> 'line_user_id', '');
$$;

create or replace function private.my_family_ids()
returns setof uuid
language sql
stable
security definer
set search_path = ''
as $$
  select fm.family_id
  from public.family_members fm
  join public.users u on u.id = fm.user_id
  where u.line_user_id = private.current_line_user_id();
$$;
revoke all on function private.my_family_ids() from public, anon;
grant usage on schema private to authenticated;
grant execute on function private.my_family_ids() to authenticated;
grant execute on function private.current_line_user_id() to authenticated;

create policy "members read own families" on public.families
  for select to authenticated
  using (id in (select private.my_family_ids()));

create policy "read self" on public.users
  for select to authenticated
  using (line_user_id = (select private.current_line_user_id()));

create policy "members read memberships" on public.family_members
  for select to authenticated
  using (family_id in (select private.my_family_ids()));

create policy "members read reports" on public.medical_reports
  for select to authenticated
  using (family_id in (select private.my_family_ids()) and status = 'confirmed');

create policy "members read daily" on public.daily_records
  for select to authenticated
  using (family_id in (select private.my_family_ids()));

create policy "members write daily" on public.daily_records
  for insert to authenticated
  with check (family_id in (select private.my_family_ids()));

create policy "members update daily" on public.daily_records
  for update to authenticated
  using (family_id in (select private.my_family_ids()))
  with check (family_id in (select private.my_family_ids()));

create policy "read global and family rules" on public.care_rules
  for select to authenticated
  using (family_id is null or family_id in (select private.my_family_ids()));

create policy "members read advices" on public.ai_advices
  for select to authenticated
  using (family_id in (select private.my_family_ids()));

create policy "members read reminders" on public.reminders
  for select to authenticated
  using (family_id in (select private.my_family_ids()));

insert into storage.buckets (id, name, public, file_size_limit, allowed_mime_types)
values ('media', 'media', false, 10485760, array['image/png', 'image/jpeg', 'audio/mpeg', 'audio/mp4'])
on conflict (id) do nothing;
