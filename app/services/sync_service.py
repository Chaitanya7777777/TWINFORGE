import asyncio

from app.connectors.simulator import get_snapshot
from app.twin.mapper import simulator_asset_to_twin
from app.twin.registry import TwinRegistry


class SyncService:
    def __init__(self, registry: TwinRegistry):
        self.registry = registry
        self.running = False

    async def sync_once(self):
        snapshot = await get_snapshot()

        self.registry.mark_sync_success()

        run_id = snapshot["run_id"]

        if self.registry.current_run_id != run_id:
            self.registry.reset_for_new_run(run_id)

        accepted = 0
        rejected = 0

        for asset in snapshot["assets"]:
            twin = simulator_asset_to_twin(asset)

            if self.registry.update(twin):
                accepted += 1
            else:
                rejected += 1

        return {
            "run_id": run_id,
            "accepted": accepted,
            "rejected": rejected
        }

    async def run_forever(self):
        self.running = True

        while self.running:
            try:
                await self.sync_once()

            except Exception as e:
                self.registry.mark_sync_failure()
                print(f"Simulator sync failed: {e}")

            await asyncio.sleep(1)

    def stop(self):
        self.running = False