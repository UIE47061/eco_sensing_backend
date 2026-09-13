import hashlib
import secrets
from datetime import datetime, timedelta, timezone
from typing import Any
from uuid import UUID

import jwt
from fastapi import Header, HTTPException

from db.supabase import request_supabase
from services.auth import JWT_ALGORITHM, _jwt_secret

AGENT_ACCESS_TOKEN_EXPIRE_SECONDS = 60 * 60  # 1 小時,v26 §4.4.4,不可改
AGENT_REFRESH_TOKEN_EXPIRE_DAYS = 90  # v26 §4.4.4 定案,到期需重新綁定,不輪換
BINDING_CODE_TTL_SECONDS = 5 * 60  # v26 §4.4.2/§4.4.4 定案


def generate_device_secret() -> str:
    return secrets.token_urlsafe(32)


def hash_device_secret(secret: str) -> str:
    return hashlib.sha256(secret.encode("utf-8")).hexdigest()


def generate_agent_refresh_token() -> str:
    return secrets.token_urlsafe(48)


def hash_agent_refresh_token(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def generate_binding_code() -> str:
    return secrets.token_urlsafe(8)


def generate_id_token() -> str:
    return secrets.token_urlsafe(32)


def create_agent_access_token(device_binding_id: UUID) -> tuple[str, int]:
    now = datetime.now(timezone.utc)
    expires_at = now + timedelta(seconds=AGENT_ACCESS_TOKEN_EXPIRE_SECONDS)
    payload = {
        "sub": str(device_binding_id),
        "type": "agent_access",
        "iat": now,
        "exp": expires_at,
    }
    token = jwt.encode(payload, _jwt_secret(), algorithm=JWT_ALGORITHM)
    return token, AGENT_ACCESS_TOKEN_EXPIRE_SECONDS


def decode_agent_access_token(token: str) -> UUID:
    try:
        payload = jwt.decode(token, _jwt_secret(), algorithms=[JWT_ALGORITHM])
    except jwt.ExpiredSignatureError as exc:
        raise HTTPException(
            status_code=401,
            detail="Agent access token expired",
            headers={"WWW-Authenticate": "Bearer"},
        ) from exc
    except jwt.InvalidTokenError as exc:
        raise HTTPException(
            status_code=401,
            detail="Invalid agent access token",
            headers={"WWW-Authenticate": "Bearer"},
        ) from exc

    if payload.get("type") != "agent_access":
        raise HTTPException(
            status_code=401,
            detail="Invalid agent access token",
            headers={"WWW-Authenticate": "Bearer"},
        )
    subject = payload.get("sub")
    if not subject:
        raise HTTPException(
            status_code=401,
            detail="Invalid agent access token",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return UUID(subject)


def upsert_device(device_id: UUID, display_name: str | None = None) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "id": str(device_id),
        "type": "agent",
        "status": "active",
        "last_seen": datetime.now(timezone.utc).isoformat(),
    }
    if display_name is not None:
        payload["display_name"] = display_name
    data = request_supabase(
        "POST",
        "device",
        json=payload,
        prefer="resolution=merge-duplicates,return=representation",
    )
    return data[0]


def find_pending_binding_code_for_device(device_id: UUID) -> dict[str, Any] | None:
    data = request_supabase(
        "GET",
        "binding_code",
        params={
            "select": "*",
            "device_id": f"eq.{device_id}",
            "status": "eq.pending",
            "limit": 1,
        },
    )
    return data[0] if data else None


def create_or_refresh_binding_code(device_id: UUID) -> tuple[dict[str, Any], str]:
    """索取綁定碼:找該裝置既有 pending 記錄就更新,否則新建(v26 §4.4.2 upsert 而非盲插)。"""
    code = generate_binding_code()
    device_secret = generate_device_secret()
    now = datetime.now(timezone.utc)
    expires_at = now + timedelta(seconds=BINDING_CODE_TTL_SECONDS)

    payload = {
        "code": code,
        "device_id": str(device_id),
        "employee_id": None,
        "device_binding_id": None,
        "status": "pending",
        "device_secret_hash": hash_device_secret(device_secret),
        "expires_at": expires_at.isoformat(),
        "consumed_at": None,
    }

    existing = find_pending_binding_code_for_device(device_id)
    if existing is None:
        data = request_supabase(
            "POST",
            "binding_code",
            json=payload,
            prefer="return=representation",
        )
        row = data[0]
    else:
        data = request_supabase(
            "PATCH",
            "binding_code",
            params={"id": f"eq.{existing['id']}"},
            json=payload,
            prefer="return=representation",
        )
        row = data[0]

    return row, device_secret


def find_binding_code(code: str) -> dict[str, Any] | None:
    data = request_supabase(
        "GET",
        "binding_code",
        params={"select": "*", "code": f"eq.{code}", "limit": 1},
    )
    return data[0] if data else None


def create_device_binding(employee_id: UUID, device_id: UUID) -> dict[str, Any]:
    payload = {
        "employee_id": str(employee_id),
        "device_id": str(device_id),
        "id_token": generate_id_token(),
        "status": "active",
        "bound_at": datetime.now(timezone.utc).isoformat(),
    }
    data = request_supabase(
        "POST",
        "device_binding",
        json=payload,
        prefer="return=representation",
    )
    return data[0]


def consume_binding_code(binding_code_id: UUID, employee_id: UUID, device_binding_id: UUID) -> None:
    request_supabase(
        "PATCH",
        "binding_code",
        params={"id": f"eq.{binding_code_id}"},
        json={
            "status": "consumed",
            "employee_id": str(employee_id),
            "device_binding_id": str(device_binding_id),
            "consumed_at": datetime.now(timezone.utc).isoformat(),
        },
    )


def find_device_binding_by_id(device_binding_id: UUID) -> dict[str, Any] | None:
    data = request_supabase(
        "GET",
        "device_binding",
        params={"select": "*", "id": f"eq.{device_binding_id}", "limit": 1},
    )
    return data[0] if data else None


def find_device_binding_by_id_token(id_token: str) -> dict[str, Any] | None:
    data = request_supabase(
        "GET",
        "device_binding",
        params={"select": "*", "id_token": f"eq.{id_token}", "limit": 1},
    )
    return data[0] if data else None


def find_active_device_binding_by_refresh_token(refresh_token: str) -> dict[str, Any] | None:
    data = request_supabase(
        "GET",
        "device_binding",
        params={
            "select": "*",
            "refresh_token_hash": f"eq.{hash_agent_refresh_token(refresh_token)}",
            "status": "eq.active",
            "limit": 1,
        },
    )
    return data[0] if data else None


def touch_device_binding_last_seen(device_binding_id: UUID) -> None:
    request_supabase(
        "PATCH",
        "device_binding",
        params={"id": f"eq.{device_binding_id}"},
        json={"last_seen": datetime.now(timezone.utc).isoformat()},
    )


def revoke_device_binding(device_binding_id: UUID) -> bool:
    data = request_supabase(
        "PATCH",
        "device_binding",
        params={"id": f"eq.{device_binding_id}", "status": "eq.active"},
        json={"status": "revoked", "revoked_at": datetime.now(timezone.utc).isoformat()},
        prefer="return=representation",
    )
    return bool(data)


_REFRESH_DELIVERY_GRACE = timedelta(minutes=10)
_pending_refresh_delivery: dict[str, tuple[str, datetime]] = {}


def mint_tokens_for_binding_code(binding_code_row: dict[str, Any]) -> tuple[str, str | None, int]:
    """端點③首次核銷時現場簽發:Access 每次重簽,Refresh 只在尚未寫入時生成一次。

    Refresh Token 明文不落地(僅雜湊寫入 device_binding),但為了讓「DB 已寫入雜湊、
    HTTP 回應卻在傳輸中遺失」時 Agent 還能重試取回,生成後短暫(10 分鐘)存於行程記憶體,
    寬限期內的重複輪詢仍會拿到同一枚明文;寬限期後才真正遺失,需重新走一次綁定流程。
    """
    device_binding_id = UUID(binding_code_row["device_binding_id"])
    device_binding = find_device_binding_by_id(device_binding_id)
    if device_binding is None:
        raise HTTPException(status_code=500, detail="Device binding not found for consumed code")

    access_token, expires_in = create_agent_access_token(device_binding_id)

    key = str(device_binding_id)
    now = datetime.now(timezone.utc)
    refresh_token: str | None = None

    if not device_binding.get("refresh_token_hash"):
        refresh_token = generate_agent_refresh_token()
        request_supabase(
            "PATCH",
            "device_binding",
            params={"id": f"eq.{device_binding_id}"},
            json={"refresh_token_hash": hash_agent_refresh_token(refresh_token)},
        )
        _pending_refresh_delivery[key] = (refresh_token, now + _REFRESH_DELIVERY_GRACE)
    else:
        cached = _pending_refresh_delivery.get(key)
        if cached and cached[1] > now:
            refresh_token = cached[0]

    return access_token, refresh_token, expires_in


def get_current_device_binding(authorization: str | None = Header(default=None)) -> dict[str, Any]:
    """裝置粒度的 Bearer 驗證。與 get_current_employee 的關鍵差異:每次請求都重查 DB 確認
    status=='active',不能只信 JWT 簽章——撤銷必須在上傳回應當下就反映,見 v26 §4.4.2 撤銷機制。
    """
    if not authorization or not authorization.lower().startswith("bearer "):
        raise HTTPException(
            status_code=401,
            detail="Missing bearer token",
            headers={"WWW-Authenticate": "Bearer"},
        )
    token = authorization.split(" ", 1)[1].strip()
    device_binding_id = decode_agent_access_token(token)

    device_binding = find_device_binding_by_id(device_binding_id)
    if device_binding is None or device_binding.get("status") != "active":
        raise HTTPException(
            status_code=403,
            detail="Device binding revoked",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return device_binding
