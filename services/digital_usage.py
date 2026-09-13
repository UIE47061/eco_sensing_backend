from datetime import date, datetime
from typing import Any
from uuid import UUID

import asyncpg
from fastapi import HTTPException

_COMPUTER_UPSERT = """
insert into public.digital_usage (
    employee_id, device_id, usage_date, path_type, sensing_mode, collected_at,
    pc_active_hours, pc_idle_hours, pc_avg_cpu_util, cpu_model
) values ($1, $2, $3, 'computer', 'auto', $4, $5, $6, $7, $8)
on conflict (employee_id, usage_date, path_type, device_id)
    where path_type = 'computer' and sensing_mode = 'auto'
do update set
    collected_at = excluded.collected_at,
    pc_active_hours = excluded.pc_active_hours,
    pc_idle_hours = excluded.pc_idle_hours,
    pc_avg_cpu_util = excluded.pc_avg_cpu_util,
    cpu_model = excluded.cpu_model
where excluded.collected_at > public.digital_usage.collected_at
"""

_DRIVE_UPSERT = """
insert into public.digital_usage (
    employee_id, device_id, usage_date, path_type, sensing_mode, collected_at,
    drive_usage_gb, drive_trash_gb
) values ($1, $2, $3, 'drive', 'auto', $4, $5, $6)
on conflict (employee_id, usage_date, path_type)
    where path_type = 'drive' and sensing_mode = 'auto'
do update set
    collected_at = excluded.collected_at,
    drive_usage_gb = excluded.drive_usage_gb,
    drive_trash_gb = excluded.drive_trash_gb
where excluded.collected_at > public.digital_usage.collected_at
"""

_PRINTER_UPSERT_BY_SERIAL = """
insert into public.digital_usage (
    employee_id, device_id, usage_date, path_type, sensing_mode, collected_at,
    printer_serial, printer_page_counter, print_pages, printer_identity_unknown
) values ($1, $2, $3, 'printer', 'auto', $4, $5, $6, $7, false)
on conflict (employee_id, usage_date, path_type, printer_serial)
    where path_type = 'printer' and sensing_mode = 'auto'
do update set
    collected_at = excluded.collected_at,
    printer_page_counter = excluded.printer_page_counter,
    print_pages = excluded.print_pages
where excluded.collected_at > public.digital_usage.collected_at
"""

_PRINTER_UPSERT_UNKNOWN = """
insert into public.digital_usage (
    employee_id, device_id, usage_date, path_type, sensing_mode, collected_at,
    printer_page_counter, print_pages, printer_identity_unknown
) values ($1, $2, $3, 'printer', 'auto', $4, $5, $6, true)
on conflict (employee_id, usage_date, path_type, device_id)
    where path_type = 'printer' and sensing_mode = 'auto' and printer_serial is null
do update set
    collected_at = excluded.collected_at,
    printer_page_counter = excluded.printer_page_counter,
    print_pages = excluded.print_pages
where excluded.collected_at > public.digital_usage.collected_at
"""

_LAST_PRINTER_COUNTER_BY_SERIAL = """
select printer_page_counter from public.digital_usage
where employee_id = $1 and path_type = 'printer' and sensing_mode = 'auto' and printer_serial = $2
order by collected_at desc
limit 1
"""

_LAST_PRINTER_COUNTER_UNKNOWN = """
select printer_page_counter from public.digital_usage
where employee_id = $1 and path_type = 'printer' and sensing_mode = 'auto'
    and device_id = $2 and printer_serial is null
order by collected_at desc
limit 1
"""


def _parse_datetime(value: Any) -> datetime:
    if isinstance(value, datetime):
        return value
    return datetime.fromisoformat(str(value).replace("Z", "+00:00"))


def _parse_date(value: Any) -> date:
    if isinstance(value, date):
        return value
    return date.fromisoformat(str(value))


async def upsert_batch(
    pool: asyncpg.Pool,
    employee_id: UUID,
    device_id: UUID,
    events: list[dict[str, Any]],
) -> int:
    try:
        async with pool.acquire() as conn:
            async with conn.transaction():
                for event in events:
                    await _upsert_event(conn, employee_id, device_id, event)
    except asyncpg.PostgresError as exc:
        raise HTTPException(status_code=502, detail=f"Database upsert failed: {exc}") from exc

    return len(events)


async def _upsert_event(
    conn: asyncpg.Connection,
    employee_id: UUID,
    device_id: UUID,
    event: dict[str, Any],
) -> None:
    path_type = event["path_type"]
    usage_date = _parse_date(event["usage_date"])
    collected_at = _parse_datetime(event["collected_at"])

    if path_type == "computer":
        await conn.execute(
            _COMPUTER_UPSERT,
            employee_id,
            device_id,
            usage_date,
            collected_at,
            event.get("pc_active_hours"),
            event.get("pc_idle_hours"),
            event.get("pc_avg_cpu_util"),
            event.get("cpu_model"),
        )
        return

    if path_type == "drive":
        await conn.execute(
            _DRIVE_UPSERT,
            employee_id,
            device_id,
            usage_date,
            collected_at,
            event.get("drive_usage_gb"),
            event.get("drive_trash_gb"),
        )
        return

    if path_type == "printer":
        await _upsert_printer_event(conn, employee_id, device_id, usage_date, collected_at, event)
        return

    raise HTTPException(status_code=422, detail=f"Unknown path_type: {path_type!r}")


async def _upsert_printer_event(
    conn: asyncpg.Connection,
    employee_id: UUID,
    device_id: UUID,
    usage_date: date,
    collected_at: datetime,
    event: dict[str, Any],
) -> None:
    printer_serial = event.get("printer_serial")
    current_counter = event.get("printer_page_counter")

    if printer_serial:
        previous_counter = await conn.fetchval(_LAST_PRINTER_COUNTER_BY_SERIAL, employee_id, printer_serial)
    else:
        previous_counter = await conn.fetchval(_LAST_PRINTER_COUNTER_UNKNOWN, employee_id, device_id)

    print_pages: int | None = None
    if current_counter is not None and previous_counter is not None:
        delta = current_counter - previous_counter
        # 本次 < 上次視為碳粉計數器更換／韌體重置,該區間跳過(v26 §4.4.2、[D15])
        if delta >= 0:
            print_pages = delta

    if printer_serial:
        await conn.execute(
            _PRINTER_UPSERT_BY_SERIAL,
            employee_id,
            device_id,
            usage_date,
            collected_at,
            printer_serial,
            current_counter,
            print_pages,
        )
    else:
        await conn.execute(
            _PRINTER_UPSERT_UNKNOWN,
            employee_id,
            device_id,
            usage_date,
            collected_at,
            current_counter,
            print_pages,
        )
