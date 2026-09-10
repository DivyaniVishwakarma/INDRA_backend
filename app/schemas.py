from datetime import datetime
from pydantic import BaseModel, Field

class ChatRequest(BaseModel):
    message: str = Field(min_length=1, max_length=4000)
    latitude: float | None = None
    longitude: float | None = None

class DispatchRequest(BaseModel):
    team_id: str
    latitude: float
    longitude: float
    approved: bool = False
    alert_id: int | None = None
    task: str | None = None
    zone_name: str | None = None
    eta_minutes: int | None = None

class DispatchStatusUpdate(BaseModel):
    status: str  # en_route | on_site | verifying

class DispatchVerify(BaseModel):
    note: str | None = None

class ObservationIn(BaseModel):
    source: str = Field(min_length=1, max_length=40)
    latitude: float
    longitude: float
    value: float
    timestamp: datetime | None = None
    quality_score: float = Field(default=1.0, ge=0, le=1)

# ============================================================
# ADD THIS TO: backend/app/schemas.py
# (append at the end — don't change existing schemas)
# ============================================================

from pydantic import BaseModel


class RiskRequest(BaseModel):
    """
    Request body for POST /api/live/risk.
    All fields are optional — any field left out defaults to None,
    and build_features() treats a missing value as 0 (not fabricated).
    """
    rain_15m_mm: float | None = None
    rain_60m_mm: float | None = None
    rain_180m_mm: float | None = None
    elevation_m: float | None = None
    slope_pct: float | None = None
    distance_to_drain_m: float | None = None
    drainage_capacity_ratio: float | None = None
    tide_m: float | None = None
    historical_flood_frequency: float | None = None
    impervious_fraction: float | None = None

    class Config:
        json_schema_extra = {
            "example": {
                "rain_15m_mm": 8.5,
                "rain_60m_mm": 22.0,
                "rain_180m_mm": 45.0,
                "elevation_m": 4.2,
                "slope_pct": 1.1,
                "distance_to_drain_m": 35.0,
                "drainage_capacity_ratio": 0.7,
                "tide_m": 1.8,
                "historical_flood_frequency": 0.4,
                "impervious_fraction": 0.85,
            }
        }