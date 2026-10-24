import asyncio
from contextlib import asynccontextmanager
from datetime import datetime, timezone

from fastapi import FastAPI, HTTPException

from app.config import SOURCE_STALE_AFTER_SECONDS
from app.twin.registry import TwinRegistry
from app.services.sync_service import SyncService


registry = TwinRegistry()
sync_service = SyncService(registry)


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Start automatic simulator synchronization
    sync_task = asyncio.create_task(
        sync_service.run_forever()
    )

    try:
        yield
    finally:
        # Wake the polling loop and wait for it to finish cleanly.
        sync_service.stop()
        await sync_task


app = FastAPI(
    title="TWINFORGE",
    lifespan=lifespan
)


@app.get("/health")
def health():
    return {
        "status": "ok",
        "service": "TWINFORGE"
    }


@app.post("/sync")
async def sync_twins():
    result = await sync_service.sync_once()

    return {
        "status": "synced",
        **result
    }


@app.get("/api/twins")
def get_twins():
    return registry.get_all()


@app.get("/api/twins/{asset_id}")
def get_twin(asset_id: str):
    twin = registry.get(asset_id)

    if twin is None:
        raise HTTPException(
            status_code=404,
            detail="Twin not found"
        )

    return twin

@app.get("/api/source-status")
def source_status():
    sync_lag_seconds = None

    if registry.last_sync_at is not None:
        now = datetime.now(timezone.utc)
        sync_lag_seconds = (
            now - registry.last_sync_at
        ).total_seconds()

    return {
        "source": "factory_simulator",
        "connected": registry.is_source_connected(SOURCE_STALE_AFTER_SECONDS),
        "run_id": registry.current_run_id,
        "last_sync_at": registry.last_sync_at,
        "last_sync_attempt_at": registry.last_sync_attempt_at,
        "last_sync_error": registry.last_sync_error,
        "consecutive_failures": registry.consecutive_failures,
        "sync_lag_seconds": sync_lag_seconds,
        "stale_after_seconds": SOURCE_STALE_AFTER_SECONDS,
    }
