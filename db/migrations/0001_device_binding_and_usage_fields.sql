-- Sync existing databases with db/eco_sensing_erd.mmd:
--   * new tables: device_binding, binding_code
--   * elevator_trip: floor_delta, direction
--   * digital_usage: path_type, pc_idle_hours, pc_avg_cpu_util, cpu_model, drive_trash_gb
-- Idempotent: safe to re-run.

create extension if not exists pgcrypto;

create table if not exists public.device_binding (
  id uuid primary key default gen_random_uuid(),
  employee_id uuid not null references public.employee(id) on delete cascade,
  device_id uuid not null references public.device(id) on delete cascade,
  id_token text,
  status text not null default 'active',
  refresh_token_hash text,
  bound_at timestamptz not null default now(),
  last_seen timestamptz,
  revoked_at timestamptz,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create table if not exists public.binding_code (
  id uuid primary key default gen_random_uuid(),
  code text unique not null,
  device_id uuid not null references public.device(id) on delete cascade,
  employee_id uuid references public.employee(id) on delete set null,
  device_binding_id uuid references public.device_binding(id) on delete set null,
  status text not null default 'pending',
  expires_at timestamptz not null,
  consumed_at timestamptz,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

alter table public.elevator_trip
  add column if not exists floor_delta integer,
  add column if not exists direction text;

alter table public.digital_usage
  add column if not exists path_type text,
  add column if not exists pc_idle_hours numeric(8, 2) not null default 0,
  add column if not exists pc_avg_cpu_util numeric(5, 2),
  add column if not exists cpu_model text,
  add column if not exists drive_trash_gb numeric(12, 3) not null default 0;

create index if not exists idx_device_binding_employee_id on public.device_binding(employee_id);
create index if not exists idx_device_binding_device_id on public.device_binding(device_id);
create index if not exists idx_binding_code_device_id on public.binding_code(device_id);
create index if not exists idx_binding_code_employee_id on public.binding_code(employee_id);
create index if not exists idx_binding_code_device_binding_id on public.binding_code(device_binding_id);

drop trigger if exists set_device_binding_updated_at on public.device_binding;
create trigger set_device_binding_updated_at
before update on public.device_binding
for each row execute function public.set_updated_at();

drop trigger if exists set_binding_code_updated_at on public.binding_code;
create trigger set_binding_code_updated_at
before update on public.binding_code
for each row execute function public.set_updated_at();
