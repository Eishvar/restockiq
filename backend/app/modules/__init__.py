"""Feature modules. Each module exposes a FastAPI router; register it in ROUTERS."""
from fastapi import APIRouter

ROUTERS: list[APIRouter] = []
