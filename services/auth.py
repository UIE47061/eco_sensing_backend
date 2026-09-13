import hashlib
import secrets
from datetime import datetime, timedelta, timezone
from typing import Any
from uuid import UUID

import bcrypt
import jwt
from fastapi import Header, HTTPException

from db.supabase import request_supabase
from util.config import Env

JWT_ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_SECONDS = 60 * 60  # 1 小時,§1 定案,不可改
REFRESH_TOKEN_EXPIRE_DAYS = 30  # §1 定案,不輪換,不可改


def _jwt_secret() -> str:
    if not Env.JWT_SECRET:
        raise HTTPException(status_code=500, detail="JWT secret is not configured")
    return Env.JWT_SECRET


def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def verify_password(password: str, password_hash: str) -> bool:
    try:
        return bcrypt.checkpw(password.encode("utf-8"), password_hash.encode("utf-8"))
    except ValueError:
        return False


def create_access_token(employee_id: UUID) -> tuple[str, int]:
    now = datetime.now(timezone.utc)
    expires_at = now + timedelta(seconds=ACCESS_TOKEN_EXPIRE_SECONDS)
    payload = {
        "sub": str(employee_id),
        "type": "access",
        "iat": now,
        "exp": expires_at,
    }
    token = jwt.encode(payload, _jwt_secret(), algorithm=JWT_ALGORITHM)
    return token, ACCESS_TOKEN_EXPIRE_SECONDS


def decode_access_token(token: str) -> UUID:
    try:
        payload = jwt.decode(token, _jwt_secret(), algorithms=[JWT_ALGORITHM])
    except jwt.ExpiredSignatureError as exc:
        raise HTTPException(
            status_code=401,
            detail="Access token expired",
            headers={"WWW-Authenticate": "Bearer"},
        ) from exc
    except jwt.InvalidTokenError as exc:
        raise HTTPException(
            status_code=401,
            detail="Invalid access token",
            headers={"WWW-Authenticate": "Bearer"},
        ) from exc

    subject = payload.get("sub")
    if not subject:
        raise HTTPException(
            status_code=401,
            detail="Invalid access token",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return UUID(subject)


def generate_refresh_token() -> str:
    return secrets.token_urlsafe(48)


def hash_refresh_token(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def find_employee_by_email(email: str) -> dict[str, Any] | None:
    data = request_supabase(
        "GET",
        "employee",
        params={"select": "*", "email": f"eq.{email}", "limit": 1},
    )
    return data[0] if data else None


def create_app_session(employee_id: UUID, refresh_token: str) -> dict[str, Any]:
    now = datetime.now(timezone.utc)
    expires_at = now + timedelta(days=REFRESH_TOKEN_EXPIRE_DAYS)
    payload = {
        "employee_id": str(employee_id),
        "refresh_token_hash": hash_refresh_token(refresh_token),
        "status": "active",
        "expires_at": expires_at.isoformat(),
    }
    data = request_supabase(
        "POST",
        "app_session",
        json=payload,
        prefer="return=representation",
    )
    return data[0]


def find_active_session_by_refresh_token(refresh_token: str) -> dict[str, Any] | None:
    data = request_supabase(
        "GET",
        "app_session",
        params={
            "select": "*",
            "refresh_token_hash": f"eq.{hash_refresh_token(refresh_token)}",
            "status": "eq.active",
            "limit": 1,
        },
    )
    return data[0] if data else None


def touch_session_last_used(session_id: UUID) -> None:
    request_supabase(
        "PATCH",
        "app_session",
        params={"id": f"eq.{session_id}"},
        json={"last_used_at": datetime.now(timezone.utc).isoformat()},
    )


def revoke_sessions_for_employee(employee_id: UUID) -> int:
    """離職／裝置遺失:撤銷該員工所有仍 active 的 App Refresh(§5)。

    全撤銷而非挑單一裝置,因 APP_SESSION 目前無裝置識別欄(§7.2 待辦)。
    """
    data = request_supabase(
        "PATCH",
        "app_session",
        params={"employee_id": f"eq.{employee_id}", "status": "eq.active"},
        json={"status": "revoked", "revoked_at": datetime.now(timezone.utc).isoformat()},
        prefer="return=representation",
    )
    return len(data) if data else 0


def get_current_employee(authorization: str | None = Header(default=None)) -> UUID:
    if not authorization or not authorization.lower().startswith("bearer "):
        raise HTTPException(
            status_code=401,
            detail="Missing bearer token",
            headers={"WWW-Authenticate": "Bearer"},
        )
    token = authorization.split(" ", 1)[1].strip()
    return decode_access_token(token)
