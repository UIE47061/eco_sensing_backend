-- Sync existing databases with db/eco_sensing_erd.mmd (context doc v26 §4.4 [D14]/[D15]/[D16]):
--   * device: display_name
--   * digital_usage: device_id, sensing_mode, collected_at, printer_serial, printer_page_counter
--   * digital_usage: path_type/sensing_mode/collected_at become NOT NULL; pc_*/print_pages/drive_*
--     become nullable (Agent 純感測、後端計算欄位可為 NULL,不再套 not-null default 0)
--   * digital_usage: four partial unique indexes for idempotent upsert conflict targets
--     (uq_digital_usage_device / _printer / _printer_manual / _account, see §5.1)
-- Idempotent: safe to re-run. Assumes no production data (context doc v26 §5.1: DB currently has
-- no rows, schema adjustment carries no migration cost).

create extension if not exists pgcrypto;

alter table public.device
  add column if not exists display_name text;

alter table public.digital_usage
  add column if not exists device_id uuid references public.device(id) on delete set null,
  add column if not exists sensing_mode text,
  add column if not exists collected_at timestamptz,
  add column if not exists printer_serial text,
  add column if not exists printer_page_counter integer;

alter table public.digital_usage
  alter column path_type set not null,
  alter column sensing_mode set not null,
  alter column collected_at set not null,
  alter column pc_active_hours drop not null,
  alter column pc_active_hours drop default,
  alter column pc_idle_hours drop not null,
  alter column pc_idle_hours drop default,
  alter column print_pages drop not null,
  alter column print_pages drop default,
  alter column drive_usage_gb drop not null,
  alter column drive_usage_gb drop default,
  alter column drive_trash_gb drop not null,
  alter column drive_trash_gb drop default;

create index if not exists idx_digital_usage_device_id on public.digital_usage(device_id);

create unique index if not exists uq_digital_usage_device on public.digital_usage
  (employee_id, usage_date, path_type, device_id)
  where path_type = 'computer' and sensing_mode = 'auto';

create unique index if not exists uq_digital_usage_printer on public.digital_usage
  (employee_id, usage_date, path_type, printer_serial)
  where path_type = 'printer' and sensing_mode = 'auto';

create unique index if not exists uq_digital_usage_printer_manual on public.digital_usage
  (employee_id, usage_date, path_type, sensing_mode)
  where path_type = 'printer' and sensing_mode = 'manual';

create unique index if not exists uq_digital_usage_account on public.digital_usage
  (employee_id, usage_date, path_type)
  where path_type = 'drive' and sensing_mode = 'auto';

comment on column public.digital_usage.path_type is
  '感測對象列舉(computer/printer/drive);[D12] 由 Agent 明送,不由後端推斷';
comment on column public.digital_usage.sensing_mode is
  '感測方式(auto=Agent 自動感測, manual=App 手動彙總上傳);與 path_type 正交,[D16] 新增,四個 partial unique index 皆帶此述詞避免 NULL 互不相等的去重陷阱';
comment on column public.digital_usage.collected_at is
  'Agent 採集時間戳(UTC);[D14] upsert 勝出規則 WHERE EXCLUDED.collected_at > digital_usage.collected_at 所依賴';
comment on column public.digital_usage.printer_serial is
  'SNMP 序號(prtGeneralSerialNumber → entPhysicalSerialNum → sysName 依序試);[D14] per-printer 歸鍵所依賴,手動上傳恆為 NULL';
comment on column public.digital_usage.printer_page_counter is
  '印表機壽命累計讀數(Agent 原樣上送);[D15] print_pages 由後端以本日減前一日差分計算';
comment on column public.device.display_name is
  '裝置顯示名稱(綁定時 Agent 送 hostname 或員工自填);裝置分項一旦對使用者可見,UUID 無法辨識是哪一台,[D14] 補入';
