import requests

from util.config import Env


def test_supabase_connection() -> dict[str, object]:
    if not Env.SUPABASE_URL:
        return {
            "ok": False,
            "status_code": None,
            "message": "SUPABASE_URL is missing",
        }

    api_key = Env.SUPABASE_KEY or Env.SUPABASE_ANON_KEY
    if not api_key:
        return {
            "ok": False,
            "status_code": None,
            "message": "SUPABASE_KEY or SUPABASE_ANON_KEY is missing",
        }

    url = Env.SUPABASE_URL.rstrip("/") + "/auth/v1/health"
    headers = {
        "apikey": api_key,
    }

    try:
        response = requests.get(url, headers=headers, timeout=10)
    except requests.RequestException as exc:
        return {
            "ok": False,
            "status_code": None,
            "message": "Could not connect to Supabase",
            "error": str(exc),
        }

    return {
        "ok": response.ok,
        "status_code": response.status_code,
        "key_type": "publishable" if api_key.startswith("sb_publishable_") else "legacy",
        "message": "Supabase connection successful"
        if response.ok
        else "Supabase connection failed",
    }
