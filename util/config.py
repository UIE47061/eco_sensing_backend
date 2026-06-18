import os

from dotenv import find_dotenv, load_dotenv

load_dotenv(find_dotenv(), override=False)


class Env:
    PROJECT_NAME: str = os.getenv("PROJECT_NAME", "eco_sensing_backend")
    VERSION: str = os.getenv("VERSION", "0.1.0")
    DOCS_USERNAME: str = os.getenv("DOCS_USERNAME", "")
    DOCS_PASSWORD: str = os.getenv("DOCS_PASSWORD", "")
    SUPABASE_URL: str = os.getenv("SUPABASE_URL", "")
    SUPABASE_KEY: str = os.getenv("SUPABASE_KEY", "")
    SUPABASE_ANON_KEY: str = os.getenv("SUPABASE_ANON_KEY", "")
    SUPABASE_SERVICE_ROLE_KEY: str = os.getenv("SUPABASE_SERVICE_ROLE_KEY", "")
    PORT: int = int(os.getenv("PORT", "7860"))
    RELOAD: bool = os.getenv("RELOAD", "").lower() == "true"
