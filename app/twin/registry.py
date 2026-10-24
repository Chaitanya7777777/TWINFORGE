from datetime import datetime, timezone

from app.twin.models import MachineTwin


class TwinRegistry:
    def __init__(self):
        self.twins: dict[str, MachineTwin] = {}

        self.current_run_id: str | None = None

        self.last_sync_at: datetime | None = None
        self.source_connected: bool = False

    def reset_for_new_run(self, run_id: str):
        self.twins.clear()
        self.current_run_id = run_id

    def update(self, twin: MachineTwin):
        existing = self.twins.get(twin.asset_id)

        if existing is None:
            self.twins[twin.asset_id] = twin
            return True

        if twin.sequence <= existing.sequence:
            return False

        self.twins[twin.asset_id] = twin
        return True

    def mark_sync_success(self):
        self.last_sync_at = datetime.now(timezone.utc)
        self.source_connected = True

    def mark_sync_failure(self):
        self.source_connected = False

    def get(self, asset_id: str):
        return self.twins.get(asset_id)

    def get_all(self):
        return list(self.twins.values())