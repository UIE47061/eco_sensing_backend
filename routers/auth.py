from datetime import datetime, timezone

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from services.auth import (
    create_access_token,
    create_app_session,
    find_active_session_by_refresh_token,
    find_employee_by_email,
    generate_refresh_token,
    touch_session_last_used,
    verify_password,
)

router = APIRouter(prefix="/api/auth", tags=["Auth"])


class LoginRequest(BaseModel):
    email: str = Field(..., examples=["alex@example.com"])
    password: str = Field(..., examples=["test1234"])


class TokenRefreshRequest(BaseModel):
    refresh_token: str


class LoginResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    expires_in: int


class TokenRefreshResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in: int


def _invalid_credentials() -> HTTPException:
    return HTTPException(status_code=401, detail="Invalid email or password")


def _parse_timestamptz(value: str) -> datetime:
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


@router.post("/login", response_model=LoginResponse)
def login(payload: LoginRequest) -> LoginResponse:
    employee = find_employee_by_email(payload.email)
    if not employee or not employee.get("password_hash"):
        raise _invalid_credentials()
    if not verify_password(payload.password, employee["password_hash"]):
        raise _invalid_credentials()

    access_token, expires_in = create_access_token(employee["id"])
    refresh_token = generate_refresh_token()
    create_app_session(employee["id"], refresh_token)

    return LoginResponse(
        access_token=access_token,
        refresh_token=refresh_token,
        expires_in=expires_in,
    )


@router.post("/token/refresh", response_model=TokenRefreshResponse)
def refresh_token(payload: TokenRefreshRequest) -> TokenRefreshResponse:
    session = find_active_session_by_refresh_token(payload.refresh_token)
    if not session:
        raise HTTPException(status_code=401, detail="Refresh token invalid or revoked")

    if _parse_timestamptz(session["expires_at"]) <= datetime.now(timezone.utc):
        raise HTTPException(status_code=401, detail="Refresh token expired")

    access_token, expires_in = create_access_token(session["employee_id"])
    touch_session_last_used(session["id"])

    return TokenRefreshResponse(access_token=access_token, expires_in=expires_in)
