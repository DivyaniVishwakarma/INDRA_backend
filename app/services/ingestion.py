"""
Live data ingestion for INDRA.

This module bridges the "live fetch" layer (imd.py, bmc_gis.py) with the
"read" layer (routes.py) by periodically pulling data and persisting it
into the database tables that /api/dashboard/summary, /api/alerts, etc.
actually read from. Without this, those tables stay empty forever and the
dashboard always shows 0 / no_data, even though the API calls return 200 OK.

Design:
- Rainfall: try the real IMD API first (imd.fetch_current_api()). If it is
  not configured, unreachable, or its response doesn't match the parser
  below, fall back to a clearly-labeled simulated series
  (source="SIMULATED_FALLBACK", is_observed=False) so the demo never shows
  zero/no_data.
- Water level: no real sensor feed exists yet, so levels are derived from
  recent rainfall intensity (also labeled SIMULATED_FALLBACK).
- Drainage flow: BMC GIS only gives static infrastructure (drains/manholes),
  not live flow. current_flow_lps is derived from recent rainfall so
  utilization % moves realistically during the demo.
- Alerts: generated automatically when a spatial cell's computed risk is
  high/critical and no recent unacknowledged alert already exists nearby.

Wire this into main.py's startup event (see bottom of file for the snippet).
"""
from __future__ import annotations

import random
from datetime import datetime, timedelta, timezone

from sqlalchemy import desc
from sqlalchemy.orm import Session

from app.data import imd
from app.db.models import Alert, DrainageAsset, RainfallObservation, SpatialCell, WaterObservation
from app.services.analytics import all_cells

# ---------------------------------------------------------------------------
# Rainfall ingestion
# ---------------------------------------------------------------------------

def _parse_imd_payload(payload: dict) -> list[dict]:
    """
    Best-effort parser for whatever IMD_CURRENT_API_URL returns.

    IMPORTANT: adjust the key names below once you've confirmed your actual
    endpoint's response shape (print(payload) once in a test call and check).
    Expected internal shape after parsing:
        [{"station_id": str, "rain_15m_mm": float, "rain_60m_mm": float,
          "rain_180m_mm": float}, ...]
    """
    records = payload.get("data") or payload.get("stations") or payload.get("results") or []
    parsed = []
    for row in records:
        station_id = row.get("station_id") or row.get("id") or row.get("station")
        if not station_id:
            continue
        parsed.append({
            "station_id": station_id,
            "rain_15m_mm": row.get("rain_15m_mm") or row.get("rain_15m"),
            "rain_60m_mm": row.get("rain_60m_mm") or row.get("rain_60m") or row.get("rainfall"),
            "rain_180m_mm": row.get("rain_180m_mm") or row.get("rain_180m"),
        })
    return parsed


def _simulate_rainfall_burst(hour: int) -> float:
    """Demo-mode: guaranteed heavy monsoon-burst values (for presentation)."""
    return round(max(0.0, random.gauss(78.0, 12.0)), 1)


async def ingest_rainfall(db: Session) -> dict:
    real_data = None
    try:
        payload = await imd.fetch_current_api()
        if payload:
            real_data = _parse_imd_payload(payload)
    except Exception:
        real_data = None

    now = datetime.now(timezone.utc)
    written = 0

    if real_data:
        for row in real_data:
            station = imd.STATIONS.get(row["station_id"])
            if not station:
                continue
            db.add(RainfallObservation(
                source="IMD",
                station_id=row["station_id"],
                latitude=station["lat"],
                longitude=station["lon"],
                rain_15m_mm=row.get("rain_15m_mm"),
                rain_60m_mm=row.get("rain_60m_mm"),
                rain_180m_mm=row.get("rain_180m_mm"),
                timestamp=now,
                is_observed=True,
            ))
            written += 1

    if not written:
        # Fallback: clearly labeled simulated rainfall so the dashboard keeps
        # moving during the demo even if IMD isn't configured/reachable, or
        # its response didn't match the parser above.
        for station_id, station in imd.STATIONS.items():
            r60 = _simulate_rainfall_burst(now.hour)
            db.add(RainfallObservation(
                source="SIMULATED_FALLBACK",
                station_id=station_id,
                latitude=station["lat"],
                longitude=station["lon"],
                rain_15m_mm=round(r60 / 4, 1),
                rain_60m_mm=r60,
                rain_180m_mm=round(r60 * 2.2, 1),
                timestamp=now,
                is_observed=False,
            ))
            written += 1

    db.commit()
    return {"source": "IMD" if real_data else "SIMULATED_FALLBACK", "rows_written": written}


# ---------------------------------------------------------------------------
# Water level simulation (no real sensor feed available yet)
# ---------------------------------------------------------------------------

def simulate_water_levels(db: Session) -> int:
    from app.services.analytics import _latest_rain

    now = datetime.now(timezone.utc)
    written = 0
    for cell in db.query(SpatialCell).all():
        rain = _latest_rain(db, cell.latitude, cell.longitude)
        intensity = rain.rain_60m_mm if rain and rain.rain_60m_mm is not None else 0.0

        # Historical-flood-prone zones (Sion, Kurla) accumulate water faster
        # for the SAME rainfall than low-risk zones (Borivali) — this is what
        # makes different zones genuinely differ, not just random jitter.
        vulnerability = 1.0 + (cell.historical_flood_frequency or 0.0) * 0.6
        base = intensity * 1.8 * vulnerability

        level_cm = max(0.0, round(base + random.uniform(-3, 3), 1))
        db.add(WaterObservation(
            source="SIMULATED_FALLBACK",
            sensor_id=f"sim-{cell.id}",
            latitude=cell.latitude,
            longitude=cell.longitude,
            level_cm=level_cm,
            timestamp=now,
            is_observed=False,
        ))
        written += 1

    db.commit()
    return written


# ---------------------------------------------------------------------------
# Drainage stress refresh
# ---------------------------------------------------------------------------

def refresh_drainage_stress(db: Session) -> int:
    from app.services.analytics import _latest_rain

    updated = 0
    for asset in db.query(DrainageAsset).all():
        if not asset.capacity_lps or asset.latitude is None or asset.longitude is None:
            continue

        rain = _latest_rain(db, asset.latitude, asset.longitude)
        intensity = rain.rain_60m_mm if rain and rain.rain_60m_mm is not None else 0.0

        stress_fraction = min(1.0, 0.15 + (intensity / 80.0))
        jitter = random.uniform(-0.05, 0.05)
        asset.current_flow_lps = round(
            asset.capacity_lps * max(0.0, min(1.0, stress_fraction + jitter)), 1
        )
        updated += 1

    db.commit()
    return updated


# ---------------------------------------------------------------------------
# Alert generation
# ---------------------------------------------------------------------------

async def generate_alerts(db: Session, cooldown_minutes: int = 30) -> int:
    rows = await all_cells(db)          # zone_summary(db) -> all_cells(db)
    cutoff = datetime.now(timezone.utc) - timedelta(minutes=cooldown_minutes)
    created = 0

    for cell in rows:
        if cell["level"] not in ("critical", "high"):
            continue

        zone_key = cell.get("ward_name") or cell["cell_id"]
        recent = db.query(Alert).filter(
            Alert.acknowledged.is_(False),
            Alert.created_at >= cutoff,
            Alert.title.like(f"%— {zone_key}"),         # naam se dedupe, exact coords se nahi
        ).first()
        if recent:
            continue

        db.add(Alert(
            source="INDRA",
            severity=cell["level"],
            title=f"{cell['level'].title()} flood risk — {zone_key}",
            message=(
                f"Risk score {cell['score']:.2f}. Drainage utilization "
                f"{cell['drainage_utilization_pct']}%. Drivers: "
                f"{', '.join(cell.get('drivers', [])) or 'n/a'}."
            ),
            latitude=cell["latitude"],
            longitude=cell["longitude"],
            acknowledged=False,
        ))
        created += 1

    db.commit()
    return created

# ---------------------------------------------------------------------------
# Full cycle — call this on a schedule from main.py
# ---------------------------------------------------------------------------

async def run_ingestion_cycle(db: Session) -> dict:
    rainfall_result = await ingest_rainfall(db)
    water_written = simulate_water_levels(db)
    drainage_updated = refresh_drainage_stress(db)
    alerts_created = await generate_alerts(db)          # <-- await add karo
    return {
        "rainfall": rainfall_result,
        "water_observations_written": water_written,
        "drainage_assets_updated": drainage_updated,
        "alerts_created": alerts_created,
    }

# ---------------------------------------------------------------------------
# Add this to main.py (see chat message for the exact diff):
#
# import asyncio
# from app.db.session import SessionLocal
# from app.services.ingestion import run_ingestion_cycle
#
# INGESTION_INTERVAL_SECONDS = 120
#
# async def _ingestion_loop():
#     while True:
#         db = SessionLocal()
#         try:
#             await run_ingestion_cycle(db)
#         except Exception as exc:
#             print(f"[ingestion] cycle failed: {exc}")
#         finally:
#             db.close()
#         await asyncio.sleep(INGESTION_INTERVAL_SECONDS)
#
# @app.on_event("startup")
# async def start_ingestion():
#     asyncio.create_task(_ingestion_loop())
# ---------------------------------------------------------------------------