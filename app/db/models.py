from datetime import datetime
from sqlalchemy import Boolean, DateTime, Float, Integer, String, Text, Index
from sqlalchemy.orm import Mapped, mapped_column
from app.db.session import Base

class SpatialCell(Base):
    __tablename__ = "spatial_cells"
    id: Mapped[str] = mapped_column(String(80), primary_key=True)
    latitude: Mapped[float] = mapped_column(Float, index=True)
    longitude: Mapped[float] = mapped_column(Float, index=True)
    ward_name: Mapped[str | None] = mapped_column(String(120), nullable=True, index=True)
    elevation_m: Mapped[float | None] = mapped_column(Float, nullable=True)
    slope_pct: Mapped[float | None] = mapped_column(Float, nullable=True)
    impervious_fraction: Mapped[float | None] = mapped_column(Float, nullable=True)
    historical_flood_frequency: Mapped[float] = mapped_column(Float, default=0.0)

class RainfallObservation(Base):
    __tablename__ = "rainfall_observations"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    source: Mapped[str] = mapped_column(String(40), index=True)
    station_id: Mapped[str | None] = mapped_column(String(80), nullable=True, index=True)
    latitude: Mapped[float] = mapped_column(Float, index=True)
    longitude: Mapped[float] = mapped_column(Float, index=True)
    rain_15m_mm: Mapped[float | None] = mapped_column(Float, nullable=True)
    rain_60m_mm: Mapped[float | None] = mapped_column(Float, nullable=True)
    rain_180m_mm: Mapped[float | None] = mapped_column(Float, nullable=True)
    timestamp: Mapped[datetime] = mapped_column(DateTime, index=True)
    quality_score: Mapped[float] = mapped_column(Float, default=1.0)
    is_observed: Mapped[bool] = mapped_column(Boolean, default=True)

class WaterObservation(Base):
    __tablename__ = "water_observations"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    source: Mapped[str] = mapped_column(String(40), index=True)
    sensor_id: Mapped[str | None] = mapped_column(String(80), nullable=True, index=True)
    latitude: Mapped[float] = mapped_column(Float, index=True)
    longitude: Mapped[float] = mapped_column(Float, index=True)
    level_cm: Mapped[float] = mapped_column(Float)
    timestamp: Mapped[datetime] = mapped_column(DateTime, index=True)
    quality_score: Mapped[float] = mapped_column(Float, default=1.0)
    is_observed: Mapped[bool] = mapped_column(Boolean, default=True)

class DrainageAsset(Base):
    __tablename__ = "drainage_assets"
    id: Mapped[str] = mapped_column(String(120), primary_key=True)
    asset_type: Mapped[str] = mapped_column(String(40), index=True)
    name: Mapped[str | None] = mapped_column(String(200), nullable=True)
    latitude: Mapped[float | None] = mapped_column(Float, nullable=True, index=True)
    longitude: Mapped[float | None] = mapped_column(Float, nullable=True, index=True)
    capacity_lps: Mapped[float | None] = mapped_column(Float, nullable=True)
    current_flow_lps: Mapped[float | None] = mapped_column(Float, nullable=True)
    ward_name: Mapped[str | None] = mapped_column(String(120), nullable=True)
    source: Mapped[str] = mapped_column(String(40), default="BMC_GIS")
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

class Alert(Base):
    __tablename__ = "alerts"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    source: Mapped[str] = mapped_column(String(40), default="INDRA")
    severity: Mapped[str] = mapped_column(String(32))
    title: Mapped[str] = mapped_column(String(200))
    message: Mapped[str] = mapped_column(Text)
    latitude: Mapped[float | None] = mapped_column(Float, nullable=True)
    longitude: Mapped[float | None] = mapped_column(Float, nullable=True)
    acknowledged: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, index=True)

class FieldTeam(Base):
    __tablename__ = "field_teams"
    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    name: Mapped[str] = mapped_column(String(120))
    status: Mapped[str] = mapped_column(String(32), default="standby")
    latitude: Mapped[float | None] = mapped_column(Float, nullable=True)
    longitude: Mapped[float | None] = mapped_column(Float, nullable=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

class PreventionAction(Base):
    __tablename__ = "prevention_actions"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    severity: Mapped[str] = mapped_column(String(32))
    action_type: Mapped[str] = mapped_column(String(64))
    description: Mapped[str] = mapped_column(Text)
    latitude: Mapped[float | None] = mapped_column(Float, nullable=True)
    longitude: Mapped[float | None] = mapped_column(Float, nullable=True)
    priority: Mapped[int] = mapped_column(Integer, default=1)
    status: Mapped[str] = mapped_column(String(32), default="recommended")
    approved: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

class Dispatch(Base):
    __tablename__ = "dispatches"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    alert_id: Mapped[int | None] = mapped_column(Integer, nullable=True, index=True)
    team_id: Mapped[str] = mapped_column(String(64), index=True)
    zone_name: Mapped[str | None] = mapped_column(String(120), nullable=True)
    task: Mapped[str] = mapped_column(String(200), default="Field verification")
    status: Mapped[str] = mapped_column(String(32), default="assigned", index=True)
    eta_minutes: Mapped[int | None] = mapped_column(Integer, nullable=True)
    verification_note: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, index=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    verified_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

Index("ix_rainfall_time_source", RainfallObservation.timestamp, RainfallObservation.source)
Index("ix_water_time_source", WaterObservation.timestamp, WaterObservation.source)