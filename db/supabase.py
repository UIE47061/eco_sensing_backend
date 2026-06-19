from typing import Any

import requests
from fastapi import HTTPException

from util.config import Env


def get_supabase_key() -> str:
    return Env.SUPABASE_SERVICE_ROLE_KEY or Env.SUPABASE_KEY or Env.SUPABASE_ANON_KEY


def get_headers(prefer: str | None = None) -> dict[str, str]:
    api_key = get_supabase_key()
    if not Env.SUPABASE_URL or not api_key:
        raise HTTPException(
            status_code=500,
            detail="Supabase credentials are not configured",
        )

    headers = {
        "apikey": api_key,
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }
    if prefer:
        headers["Prefer"] = prefer
    return headers


def request_supabase(
    method: str,
    table: str,
    *,
    params: dict[str, Any] | None = None,
    json: Any | None = None,
    prefer: str | None = None,
) -> Any:
    url = f"{Env.SUPABASE_URL.rstrip('/')}/rest/v1/{table}"

    try:
        response = requests.request(
            method=method,
            url=url,
            headers=get_headers(prefer=prefer),
            params=params,
            json=json,
            timeout=10,
        )
    except requests.RequestException as exc:
        raise HTTPException(
            status_code=502,
            detail=f"Could not connect to Supabase: {exc}",
        ) from exc

    if response.status_code >= 400:
        try:
            detail = response.json()
        except ValueError:
            detail = response.text
        raise HTTPException(status_code=response.status_code, detail=detail)

    if not response.content:
        return None
    return response.json()
