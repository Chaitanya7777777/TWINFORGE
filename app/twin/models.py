from typing import Optional, Any
from pydantic import BaseModel


class TwinTelemetry(BaseModel):
    timestamp: Optional[str] = None
    values: Optional[dict[str, Any]] = None


class TwinHealth(BaseModel):
    health_score: float
    anomaly_score: float


class TwinQuality(BaseModel):
    valid: bool
    fresh: bool
    source: str
    reason: Optional[str] = None


class TwinRelationships(BaseModel):
    upstream: Optional[str] = None
    downstream: Optional[str] = None


class MachineTwin(BaseModel):
    asset_id: str
    asset_type: str
    factory_id: str
    line_id: str

    state: str
    current_job_id: Optional[str] = None
    active_fault: Optional[str] = None
    sequence: int

    telemetry: TwinTelemetry
    health: TwinHealth
    quality: TwinQuality
    relationships: TwinRelationships