from fastapi import APIRouter

from services.supabase_test import test_supabase_connection

router = APIRouter(prefix="/api/supabase", tags=["Supabase"])


@router.get("/test")
def test_supabase() -> dict[str, object]:
    return test_supabase_connection()
