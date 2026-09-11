from datetime import datetime, timedelta, timezone
from typing import Any, Literal
from uuid import UUID

from fastapi import APIRouter, Depends, Header, HTTPException
from pydantic import BaseModel, Field

from db.pool import get_pool
from services.agent_auth import (
    AGENT_ACCESS_TOKEN_EXPIRE_SECONDS,
    AGENT_REFRESH_TOKEN_EXPIRE_DAYS,
    BINDING_CODE_TTL_SECONDS,
    consume_binding_code,
    create_agent_access_token,
    create_device_binding,
    create_or_refresh_binding_code,
    find_active_device_binding_by_refresh_token,
    find_binding_code,
    find_device_binding_by_id_token,
    get_current_device_binding,
    hash_device_secret,
    mint_tokens_for_binding_code,
    revoke_device_binding,
    touch_device_binding_last_seen,
    upsert_device,
)
from services.auth import get_current_employee
from services.digital_usage import upsert_batch

router = APIRouter(prefix="/api/agent", tags=["Agent"])


# ---- Pydantic models ----------------------------------------------------


class BindingCodeRequest(BaseModel):
    device_uuid: UUID


class BindingCodeResponse(BaseModel):
    code: str
    device_secret: str
    expires_at: datetime


class BindRequest(BaseModel):
    code: str


class BindResponse(BaseModel):
    status: Literal["consumed"] = "consumed"


class BindingCodeTokenResponse(BaseModel):
    status: Literal["pending", "consumed"]
    access_token: str | None = None
    refresh_token: str | None = None
    token_type: str = "bearer"
    expires_in: int | None = None


class AgentTokenRefreshRequest(BaseModel):
    refresh_token: str


class AgentTokenRefreshResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in: int


class RevokeResponse(BaseModel):
    revoked: bool


class DigitalUsageEvent(BaseModel):
    event_id: str
    path_type: Literal["computer", "drive", "printer"]
    usage_date: str
    collected_at: datetime
    # computer
    pc_active_hours: float | None = None
    pc_idle_hours: float | None = None
    pc_avg_cpu_util: float | None = None
    cpu_model: str | None = None
    # drive
    drive_usage_gb: float | None = None
    drive_trash_gb: float | None = None
    # printer
    printer_page_counter: int | None = None
    printer_serial: str | None = None


class DigitalUsageBatchRequest(BaseModel):
    id_token: str
    events: list[DigitalUsageEvent]


class DigitalUsageBatchResponse(BaseModel):
    accepted: int


class SensorConfigResponse(BaseModel):
    version: str = "1"
    bindingCodeTTL: int = Field(default=BINDING_CODE_TTL_SECONDS, examples=[300])
    accessTokenTTL: int = Field(default=AGENT_ACCESS_TOKEN_EXPIRE_SECONDS, examples=[3600])
    refreshTokenTTL: int = Field(
        default=AGENT_REFRESH_TOKEN_EXPIRE_DAYS * 86400, examples=[7776000]
    )
    computerUsageRecordInterval: int = 60
    driveQuotaInterval: int = 24 * 3600
    checkInterval: int = 60
    thresholdCount: int = 60
    maxAge: int = 24 * 3600
    printerPollInterval: int = 300
    uploadBatchMax: int = 720


# ---- Device binding chain (v26 §4.4.2) -----------------------------------


@router.post("/binding-code", response_model=BindingCodeResponse)
def request_binding_code(payload: BindingCodeRequest) -> BindingCodeResponse:
    upsert_device(payload.device_uuid)
    row, device_secret = create_or_refresh_binding_code(payload.device_uuid)
    return BindingCodeResponse(
        code=row["code"],
        device_secret=device_secret,
        expires_at=row["expires_at"],
    )


def _binding_not_found() -> HTTPException:
    return HTTPException(status_code=404, detail="Binding code not found or expired")


def _parse_timestamptz(value: str) -> datetime:
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


@router.post("/bind", response_model=BindResponse)
def bind_device(
    payload: BindRequest,
    employee_id: UUID = Depends(get_current_employee),
) -> BindResponse:
    binding_code = find_binding_code(payload.code)
    if binding_code is None or binding_code["status"] != "pending":
        raise _binding_not_found()
    if _parse_timestamptz(binding_code["expires_at"]) <= datetime.now(timezone.utc):
        raise _binding_not_found()

    device_binding = create_device_binding(employee_id, UUID(binding_code["device_id"]))
    consume_binding_code(UUID(binding_code["id"]), employee_id, UUID(device_binding["id"]))

    return BindResponse()


@router.get("/binding-code/{code}/token", response_model=BindingCodeTokenResponse)
def get_binding_code_token(
    code: str,
    x_device_secret: str = Header(...),
) -> BindingCodeTokenResponse:
    binding_code = find_binding_code(code)
    if binding_code is None:
        raise _binding_not_found()
    if _parse_timestamptz(binding_code["expires_at"]) <= datetime.now(timezone.utc):
        raise _binding_not_found()
    if binding_code.get("device_secret_hash") != hash_device_secret(x_device_secret):
        raise HTTPException(status_code=401, detail="Invalid device secret")

    if binding_code["status"] == "pending":
        return BindingCodeTokenResponse(status="pending")

    access_token, refresh_token, expires_in = mint_tokens_for_binding_code(binding_code)
    return BindingCodeTokenResponse(
        status="consumed",
        access_token=access_token,
        refresh_token=refresh_token,
        expires_in=expires_in,
    )


@router.post("/token/refresh", response_model=AgentTokenRefreshResponse)
def refresh_agent_token(payload: AgentTokenRefreshRequest) -> AgentTokenRefreshResponse:
    device_binding = find_active_device_binding_by_refresh_token(payload.refresh_token)
    if device_binding is None:
        raise HTTPException(status_code=401, detail="Refresh token invalid or revoked")

    bound_at = _parse_timestamptz(device_binding["bound_at"])
    if bound_at + timedelta(days=AGENT_REFRESH_TOKEN_EXPIRE_DAYS) <= datetime.now(timezone.utc):
        raise HTTPException(status_code=401, detail="Refresh token expired")

    access_token, expires_in = create_agent_access_token(UUID(device_binding["id"]))
    return AgentTokenRefreshResponse(access_token=access_token, expires_in=expires_in)


@router.post("/device-bindings/{device_binding_id}/revoke", response_model=RevokeResponse)
def revoke_device(device_binding_id: UUID) -> RevokeResponse:
    """解除裝置綁定(離職／裝置遺失/主動解綁)。呼叫者與認證未決議,比照
    organizations.py 的 revoke-sessions(見 docs/Eco-Sensing_驗證機制_端點關係表.md §4.2)。
    """
    revoked = revoke_device_binding(device_binding_id)
    return RevokeResponse(revoked=revoked)


# ---- Centralized config (v26 §4.4.4, minimal P1 slice) -------------------


@router.get("/sensor_config", response_model=SensorConfigResponse)
def get_sensor_config() -> SensorConfigResponse:
    return SensorConfigResponse()


# ---- Ingest batch (v26 §4.4.3, [D12]/[D14]/[D15]/[D16]) -------------------


@router.post("/digital-usage/batch", response_model=DigitalUsageBatchResponse)
async def create_digital_usage_batch(
    payload: DigitalUsageBatchRequest,
    device_binding: dict[str, Any] = Depends(get_current_device_binding),
) -> DigitalUsageBatchResponse:
    body_binding = find_device_binding_by_id_token(payload.id_token)
    if body_binding is None or body_binding["id"] != device_binding["id"]:
        raise HTTPException(status_code=401, detail="id_token does not match authenticated device")

    pool = get_pool()
    accepted = await upsert_batch(
        pool,
        UUID(device_binding["employee_id"]),
        UUID(device_binding["device_id"]),
        [event.model_dump(mode="json") for event in payload.events],
    )
    touch_device_binding_last_seen(UUID(device_binding["id"]))

    return DigitalUsageBatchResponse(accepted=accepted)
