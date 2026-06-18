from fastapi import APIRouter

from app.api.routes import health, sensors

api_router = APIRouter()
api_router.include_router(health.router, prefix="/health", tags=["health"])
api_router.include_router(sensors.router, prefix="/sensors", tags=["sensors"])
