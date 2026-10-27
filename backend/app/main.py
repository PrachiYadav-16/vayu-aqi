import logging
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from app.config import get_settings
from app.db import init_db
from app.ingest.pipeline import ensure_stations, ingest_live
from app.notify import scheduler
from app.routers import air, alerts, auth, me, trips

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
settings = get_settings()


@asynccontextmanager
async def lifespan(_: FastAPI):
    init_db()
    ensure_stations()
    if settings.run_scheduler:
        ingest_live()  # catch up any missed hours before serving
        scheduler.start()
    yield
    scheduler.stop()


app = FastAPI(
    title="Vayu API",
    description="Air quality forecasts, route exposure and personal alerts for Indian cities.",
    version="1.0.0",
    lifespan=lifespan,
)
app.add_middleware(GZipMiddleware, minimum_size=1024)
app.add_middleware(
    CORSMiddleware,
    allow_origins=[o.strip() for o in settings.cors_origins.split(",") if o.strip()],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
for r in (auth.router, me.router, air.router, trips.router, alerts.router):
    app.include_router(r)


@app.get("/api/health", tags=["ops"])
def health():
    return {"status": "ok"}


# Serve the built PWA when present (single-container deployment).
_dist = Path(__file__).resolve().parents[2] / "frontend" / "dist"
if _dist.exists():
    app.mount("/assets", StaticFiles(directory=_dist / "assets"), name="assets")

    @app.get("/{path:path}", include_in_schema=False)
    def spa(path: str):
        f = _dist / path
        if path and f.is_file():
            return FileResponse(f)
        return FileResponse(_dist / "index.html")
