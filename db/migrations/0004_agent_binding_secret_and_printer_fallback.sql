-- Sync existing databases with db/eco_sensing_erd.mmd (context doc v26 §4.4.2 endpoint③、印表機序號讀取段):
--   * binding_code: device_secret_hash (供端點③輪詢者身份核對)
--   * digital_usage: printer_identity_unknown (印表機三候選 OID 皆查無序號時的 fallback 標記)
--   * new partial unique index: uq_digital_usage_printer_unknown (補齊 fallback 的冪等去重鍵,
--     否則 printer_serial 為 NULL 時 Postgres 視為互不相等,ON CONFLICT 永遠不觸發)
-- Idempotent: safe to re-run.

alter table public.binding_code
  add column if not exists device_secret_hash text;

alter table public.digital_usage
  add column if not exists printer_identity_unknown boolean not null default false;

create unique index if not exists uq_digital_usage_printer_unknown on public.digital_usage
  (employee_id, usage_date, path_type, device_id)
  where path_type = 'printer' and sensing_mode = 'auto' and printer_serial is null;

comment on column public.binding_code.device_secret_hash is
  'sha256(device_secret);驗證端點③輪詢者是否為當初索取 code 的同一 Agent,v26 §4.4.2 步驟5.5';
comment on column public.digital_usage.printer_identity_unknown is
  '印表機三候選 OID 皆查無序號時,以 device_id 退回歸鍵並標記此列,v26 §4.4.2「序號讀取」段';
