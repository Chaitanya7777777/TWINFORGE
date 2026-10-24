import asyncio
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException
from datetime import datetime, timezone

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

    yield

    # Stop cleanly when TWINFORGE shuts down
    sync_service.stop()
    sync_task.cancel()


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

    return 

@app.get("/api/source-status")
def source_status():

    lag_seconds = None

    if registry.last_sync_at is not None:
        now = datetime.now(timezone.utc)

        lag_seconds = (
            now - registry.last_sync_at
        ).total_seconds()

    return {
        "source": "factory_simulator",
        "connected": registry.source_connected,
        "run_id": registry.current_run_id,
        "last_sync_at": registry.last_sync_at,
        "sync_lag_seconds": lag_seconds
    }