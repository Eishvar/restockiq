"""Feature modules. Each module exposes a FastAPI router; register it in ROUTERS."""
from fastapi import APIRouter

from app.modules.activity.router import router as activity_router
from app.modules.catalog.router import router as catalog_router
from app.modules.calendar.router import router as calendar_router
from app.modules.dashboard.router import router as dashboard_router
from app.modules.help.router import router as help_router
from app.modules.inventory.router import router as inventory_router
from app.modules.planning.router import router as planning_router
from app.modules.settings.router import router as settings_router
from app.modules.setup.router import router as setup_router

ROUTERS: list[APIRouter] = [
    settings_router, catalog_router, inventory_router, planning_router, calendar_router,
    dashboard_router, activity_router, setup_router, help_router,
]
