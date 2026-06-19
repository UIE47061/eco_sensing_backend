create extension if not exists pgcrypto;

create table if not exists public.company (
  id uuid primary key default gen_random_uuid(),
  name text not null,
  baseline_year integer,
  net_zero_year integer,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create table if not exists public.department (
  id uuid primary key default gen_random_uuid(),
  company_id uuid not null references public.company(id) on delete cascade,
  name text not null,
  primary_metric text,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  unique (company_id, name)
);

create table if not exists public.employee (
  id uuid primary key default gen_random_uuid(),
  department_id uuid not null references public.department(id) on delete restrict,
  id_token text unique,
  display_name text not null,
  email text unique not null,
  level integer not null default 1,
  carbon_coin integer not null default 0,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create table if not exists public.waste_bin (
  id uuid primary key default gen_random_uuid(),
  qr_code text unique not null,
  location text,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create table if not exists public.device (
  id uuid primary key default gen_random_uuid(),
  type text not null,
  status text not null default 'active',
  last_seen timestamptz,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create table if not exists public.emission_factor (
  id uuid primary key default gen_random_uuid(),
  category text not null,
  key text not null,
  value numeric(14, 6) not null,
  unit text not null,
  source text,
  valid_from date not null,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  unique (category, key, valid_from)
);

create table if not exists public.travel_record (
  id uuid primary key default gen_random_uuid(),
  employee_id uuid not null references public.employee(id) on delete cascade,
  factor_id uuid references public.emission_factor(id) on delete set null,
  track_type text,
  transport_mode text not null,
  origin text,
  destination text,
  travel_date date not null,
  amount numeric(14, 2),
  distance_km numeric(14, 3),
  co2e_kg numeric(14, 6),
  receipt_id text,
  status text not null default 'pending',
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create table if not exists public.waste_session (
  id uuid primary key default gen_random_uuid(),
  employee_id uuid not null references public.employee(id) on delete cascade,
  bin_id uuid not null references public.waste_bin(id) on delete restrict,
  scan_at timestamptz not null default now(),
  confirm_at timestamptz,
  status text not null default 'open',
  lock_held boolean not null default false,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create table if not exists public.waste_event (
  id uuid primary key default gen_random_uuid(),
  bin_id uuid not null references public.waste_bin(id) on delete restrict,
  session_id uuid references public.waste_session(id) on delete set null,
  device_id uuid references public.device(id) on delete set null,
  factor_id uuid references public.emission_factor(id) on delete set null,
  event_at timestamptz not null default now(),
  waste_type text not null,
  confidence numeric(5, 4),
  weight_g numeric(14, 3),
  co2e_kg numeric(14, 6),
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create table if not exists public.elevator_trip (
  id uuid primary key default gen_random_uuid(),
  employee_id uuid not null references public.employee(id) on delete cascade,
  factor_id uuid references public.emission_factor(id) on delete set null,
  ts_in timestamptz not null,
  ts_out timestamptz,
  floor_in integer not null,
  floor_out integer not null,
  co2e_kg numeric(14, 6),
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create table if not exists public.digital_usage (
  id uuid primary key default gen_random_uuid(),
  employee_id uuid not null references public.employee(id) on delete cascade,
  factor_id uuid references public.emission_factor(id) on delete set null,
  usage_date date not null,
  pc_active_hours numeric(8, 2) not null default 0,
  print_pages integer not null default 0,
  drive_usage_gb numeric(12, 3) not null default 0,
  co2e_kg numeric(14, 6),
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create index if not exists idx_department_company_id on public.department(company_id);
create index if not exists idx_employee_department_id on public.employee(department_id);
create index if not exists idx_travel_record_employee_id on public.travel_record(employee_id);
create index if not exists idx_travel_record_factor_id on public.travel_record(factor_id);
create index if not exists idx_waste_session_employee_id on public.waste_session(employee_id);
create index if not exists idx_waste_session_bin_id on public.waste_session(bin_id);
create index if not exists idx_waste_event_bin_id on public.waste_event(bin_id);
create index if not exists idx_waste_event_session_id on public.waste_event(session_id);
create index if not exists idx_waste_event_device_id on public.waste_event(device_id);
create index if not exists idx_waste_event_factor_id on public.waste_event(factor_id);
create index if not exists idx_elevator_trip_employee_id on public.elevator_trip(employee_id);
create index if not exists idx_elevator_trip_factor_id on public.elevator_trip(factor_id);
create index if not exists idx_digital_usage_employee_id on public.digital_usage(employee_id);
create index if not exists idx_digital_usage_factor_id on public.digital_usage(factor_id);

create or replace function public.set_updated_at()
returns trigger
language plpgsql
as $$
begin
  new.updated_at = now();
  return new;
end;
$$;

drop trigger if exists set_company_updated_at on public.company;
create trigger set_company_updated_at
before update on public.company
for each row execute function public.set_updated_at();

drop trigger if exists set_department_updated_at on public.department;
create trigger set_department_updated_at
before update on public.department
for each row execute function public.set_updated_at();

drop trigger if exists set_employee_updated_at on public.employee;
create trigger set_employee_updated_at
before update on public.employee
for each row execute function public.set_updated_at();

drop trigger if exists set_waste_bin_updated_at on public.waste_bin;
create trigger set_waste_bin_updated_at
before update on public.waste_bin
for each row execute function public.set_updated_at();

drop trigger if exists set_device_updated_at on public.device;
create trigger set_device_updated_at
before update on public.device
for each row execute function public.set_updated_at();

drop trigger if exists set_emission_factor_updated_at on public.emission_factor;
create trigger set_emission_factor_updated_at
before update on public.emission_factor
for each row execute function public.set_updated_at();

drop trigger if exists set_travel_record_updated_at on public.travel_record;
create trigger set_travel_record_updated_at
before update on public.travel_record
for each row execute function public.set_updated_at();

drop trigger if exists set_waste_session_updated_at on public.waste_session;
create trigger set_waste_session_updated_at
before update on public.waste_session
for each row execute function public.set_updated_at();

drop trigger if exists set_waste_event_updated_at on public.waste_event;
create trigger set_waste_event_updated_at
before update on public.waste_event
for each row execute function public.set_updated_at();

drop trigger if exists set_elevator_trip_updated_at on public.elevator_trip;
create trigger set_elevator_trip_updated_at
before update on public.elevator_trip
for each row execute function public.set_updated_at();

drop trigger if exists set_digital_usage_updated_at on public.digital_usage;
create trigger set_digital_usage_updated_at
before update on public.digital_usage
for each row execute function public.set_updated_at();
