-- Sync existing databases with db/eco_sensing_erd.mmd (App auth mechanism, §6 / §7.1 B1):
--   * new table: app_session (App Refresh token sessions)
--   * employee: add password_hash, drop id_token (redundant, superseded by device_binding.id_token)
--   * column comments for password_hash / refresh_token_hash pairs
-- Idempotent: safe to re-run. Assumes no production data depends on employee.id_token.

create extension if not exists pgcrypto;

alter table public.employee
  add column if not exists password_hash text;

alter table public.employee
  drop column if exists id_token;

create table if not exists public.app_session (
  id uuid primary key default gen_random_uuid(),
  employee_id uuid not null references public.employee(id) on delete cascade,
  refresh_token_hash text not null,
  status text not null default 'active',
  created_at timestamptz not null default now(),
  expires_at timestamptz not null,
  last_used_at timestamptz,
  revoked_at timestamptz
);

create index if not exists idx_app_session_employee_id on public.app_session(employee_id);

comment on column public.device_binding.id_token is
  '裝置粒度憑證,per-device 一枚;4.4.3 事件 ID 與 [D14] 鍵粒度所依賴';
comment on column public.device_binding.refresh_token_hash is
  'Eco-Agent Refresh 的雜湊(裝置粒度)';
comment on column public.app_session.refresh_token_hash is
  'App Refresh 的雜湊(員工手機粒度);與 device_binding.refresh_token_hash 同名、不同粒度';
comment on column public.employee.password_hash is
  '密碼雜湊(bcrypt/argon2);僅 login 驗證用,簽出 token 後不再使用';
