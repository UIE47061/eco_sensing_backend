import os
from dataclasses import dataclass


from dotenv import load_dotenv


load_dotenv()


@dataclass(frozen=True)
class Settings:
    PROJECT_NAME: str = os.getenv("PROJECT_NAME", "eco_sensing_backend")
    VERSION: str = os.getenv("VERSION", "0.1.0")
    API_PREFIX: str = os.getenv("API_PREFIX", "/api/v1")


settings = Settings()
