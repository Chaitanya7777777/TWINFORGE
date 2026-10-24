import asyncio
from contextlib import asynccontextmanager
from datetime import datetime, timezone

from fastapi import FastAPI, HTTPException, Query

from app.config import SOURCE_STALE_AFTER_SECONDS, DATABASE_URL, DATABASE_TIMEOUT_SECONDS
from app.storage.postgres import PostgresStore, PersistenceError
from app.storage.models import ObservationRecord, MachineEventRecord
from app.twin.registry import TwinRegistry
from app.services.sync_service import SyncService


registry = TwinRegistry()
store = PostgresStore(DATABASE_URL, DATABASE_TIMEOUT_SECONDS) if DATABASE_URL else None
sync_service = SyncService(registry, store=store)


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
        # Cancellation is awaited, including database transaction cleanup.
        sync_task.cancel()
        try:
            await sync_task
        except asyncio.CancelledError:
            pass
        finally:
            if store is not None:
                await store.close()


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
    try:
        result = await sync_service.sync_once()
    except PersistenceError:
        raise HTTPException(503, "Database persistence failed; snapshot not accepted") from None

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


@app.get("/api/persistence-status")
def persistence_status():
    return {
        "enabled": store is not None,
        "last_persisted_at": sync_service.last_persisted_at,
        "last_error": sync_service.last_persistence_error,
    }


async def read_history(asset_id, kind, limit, after_id, run_id):
    if store is None:
        raise HTTPException(503, "Persistence is not configured")
    try:
        return await store.history(asset_id, kind, limit, after_id, run_id)
    except PersistenceError:
        raise HTTPException(503, "Historical storage is unavailable") from None


@app.get("/api/twins/{asset_id}/telemetry", response_model=list[ObservationRecord])
async def telemetry_history(asset_id: str, limit: int = Query(100, ge=1, le=1000),
                            after_id: int = Query(0, ge=0), run_id: str | None = None):
    return await read_history(asset_id, "telemetry", limit, after_id, run_id)


@app.get("/api/twins/{asset_id}/history", response_model=list[MachineEventRecord])
async def machine_history(asset_id: str, limit: int = Query(100, ge=1, le=1000),
                          after_id: int = Query(0, ge=0), run_id: str | None = None):
    return await read_history(asset_id, "history", limit, after_id, run_id)
