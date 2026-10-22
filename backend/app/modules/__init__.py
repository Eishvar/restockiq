"""Feature modules. Each module exposes a FastAPI router; register it in ROUTERS."""
from fastapi import APIRouter

from app.modules.activity.router import router as activity_router
from app.modules.settings.router import router as settings_router

ROUTERS: list[APIRouter] = [settings_router, activity_router]
