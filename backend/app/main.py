"""RestockIQ API. One process: the API lives under /api, the built frontend at /."""
from contextlib import asynccontextmanager

from fastapi import APIRouter, FastAPI
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from app.config import APP_NAME, settings
from app.db import SessionLocal, init_db
from app.modules import ROUTERS
from app.seed.demo import ensure_demo_tenant


@asynccontextmanager
async def lifespan(_: FastAPI):
    init_db()  # create_all: adds missing tables, never alters existing ones
    with SessionLocal() as db:
        ensure_demo_tenant(db)
    yield


app = FastAPI(title=APP_NAME, lifespan=lifespan)

api = APIRouter(prefix="/api")


@api.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok", "app": APP_NAME}


app.include_router(api)
for router in ROUTERS:
    app.include_router(router, prefix="/api")

# Serve the built React app (frontend/dist) when it exists; the SPA falls back to index.html.
_dist = settings.frontend_dist
if _dist.is_dir():
    app.mount("/assets", StaticFiles(directory=_dist / "assets"), name="assets")

    @app.get("/{path:path}", include_in_schema=False)
    def spa(path: str) -> FileResponse:
        candidate = _dist / path
        if path and candidate.is_file() and _dist in candidate.resolve().parents:
            return FileResponse(candidate)
        return FileResponse(_dist / "index.html")
