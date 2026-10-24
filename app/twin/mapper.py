from app.twin.models import (
    MachineTwin,
    TwinTelemetry,
    TwinHealth,
    TwinQuality,
    TwinRelationships,
)


def simulator_asset_to_twin(asset: dict) -> MachineTwin:
    identity = asset["identity"]
    dynamic = asset["dynamic_state"]

    return MachineTwin(
        asset_id=asset["asset_id"],
        asset_type=identity["type"],
        factory_id=identity["factory_id"],
        line_id=identity["line_id"],

        state=dynamic["state"],
        current_job_id=dynamic["current_job_id"],
        active_fault=dynamic["active_fault"],
        sequence=dynamic["seq"],

        telemetry=TwinTelemetry(
            timestamp=dynamic["last_telemetry_timestamp"],
            values=dynamic["values"],
        ),

        health=TwinHealth(
            health_score=asset["health"]["health_score"],
            anomaly_score=asset["health"]["anomaly_score"],
        ),

        quality=TwinQuality(
            valid=asset["data_quality"]["valid"],
            fresh=asset["data_quality"]["fresh"],
            source=asset["data_quality"]["source"],
            reason=asset["data_quality"]["reason"],
        ),

        relationships=TwinRelationships(
            upstream=asset["relationships"]["upstream"],
            downstream=asset["relationships"]["downstream"],
        ),
    )