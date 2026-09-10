"""
One-time (idempotent) seed script for INDRA demo data.

Run with:
    python -m app.scripts.seed_data
(save this file as app/scripts/seed_data.py — create the app/scripts/
 folder with an empty __init__.py if it doesn't exist)

Populates:
  - SpatialCell: known Mumbai flood-prone zones (matches the frontend's
    risk map markers: Borivali, Andheri East, Vikhroli, Ghatkopar, Kurla,
    Sion, Dadar, Bandra, Navi Mumbai, etc.)
  - DrainageAsset: real BMC storm-water drains/manholes if the GIS API is
    reachable, otherwise synthetic assets near each zone.
  - FieldTeam: a handful of demo response teams.

Safe to re-run — skips rows that already exist.
"""
from __future__ import annotations

import asyncio
import random

from app.data import bmc_gis
from app.db.models import DrainageAsset, FieldTeam, SpatialCell
from app.db.session import Base, SessionLocal, engine

# Known flood-prone/monitored Mumbai localities (matches the risk-map UI).
# elevation_m / historical_flood_frequency are rough public-knowledge
# approximations for demo purposes, not surveyed values — replace with real
# DEM/BMC records when available.
ZONES = [
    {"id": "borivali",     "name": "Borivali",    "lat": 19.2307, "lon": 72.8567, "elevation_m": 12.0, "hist": 0.15, "impervious": 0.55},
    {"id": "andheri_east", "name": "Andheri East", "lat": 19.1197, "lon": 72.8697, "elevation_m": 9.0,  "hist": 0.35, "impervious": 0.70},
    {"id": "vikhroli",     "name": "Vikhroli",    "lat": 19.1090, "lon": 72.9290, "elevation_m": 7.0,  "hist": 0.30, "impervious": 0.60},
    {"id": "ghatkopar",    "name": "Ghatkopar",   "lat": 19.0860, "lon": 72.9080, "elevation_m": 8.0,  "hist": 0.25, "impervious": 0.65},
    {"id": "kurla",        "name": "Kurla",       "lat": 19.0726, "lon": 72.8793, "elevation_m": 5.0,  "hist": 0.55, "impervious": 0.80},
    {"id": "sion",         "name": "Sion",        "lat": 19.0400, "lon": 72.8619, "elevation_m": 3.0,  "hist": 0.75, "impervious": 0.85},
    {"id": "dadar",        "name": "Dadar",       "lat": 19.0178, "lon": 72.8478, "elevation_m": 4.0,  "hist": 0.45, "impervious": 0.80},
    {"id": "bandra",       "name": "Bandra",      "lat": 19.0596, "lon": 72.8295, "elevation_m": 6.0,  "hist": 0.30, "impervious": 0.75},
    {"id": "navi_mumbai",  "name": "Navi Mumbai", "lat": 19.0330, "lon": 73.0297, "elevation_m": 10.0, "hist": 0.10, "impervious": 0.50},
    {"id": "worli",        "name": "Worli",       "lat": 18.9986, "lon": 72.8183, "elevation_m": 5.0,  "hist": 0.30, "impervious": 0.70},
    {"id": "powai",        "name": "Powai",       "lat": 19.1176, "lon": 72.9060, "elevation_m": 11.0, "hist": 0.15, "impervious": 0.55},
    {"id": "malad",        "name": "Malad",       "lat": 19.1864, "lon": 72.8481, "elevation_m": 8.0,  "hist": 0.25, "impervious": 0.60},
]


def seed_spatial_cells(db) -> int:
    created = 0
    for z in ZONES:
        if db.query(SpatialCell).filter_by(id=z["id"]).first():
            continue
        db.add(SpatialCell(
            id=z["id"], latitude=z["lat"], longitude=z["lon"], ward_name=z["name"],
            elevation_m=z["elevation_m"], slope_pct=round(random.uniform(1, 6), 1),
            impervious_fraction=z["impervious"], historical_flood_frequency=z["hist"],
        ))
        created += 1
    db.commit()
    return created


def _synthetic_assets_for_zone(z: dict) -> list[DrainageAsset]:
    assets = []
    for i in range(2):
        capacity = random.uniform(800, 2500)
        assets.append(DrainageAsset(
            id=f"{z['id']}_synthetic_drain_{i}",
            asset_type="storm_water_drain",
            name=f"{z['name']} Drain {i + 1}",
            latitude=z["lat"] + random.uniform(-0.004, 0.004),
            longitude=z["lon"] + random.uniform(-0.004, 0.004),
            capacity_lps=round(capacity, 1),
            current_flow_lps=round(capacity * 0.2, 1),
            ward_name=z["name"],
            source="SYNTHETIC_FALLBACK",
        ))
    return assets


async def seed_drainage_assets(db) -> int:
    created = 0
    try:
        drains = await bmc_gis.get_storm_water_drains()
        manholes = await bmc_gis.get_storm_water_manholes()
        features = (drains.get("features") or []) + (manholes.get("features") or [])
        if not features:
            raise RuntimeError("BMC GIS returned no features")

        for i, f in enumerate(features):
            geom = f.get("geometry") or {}
            coords = geom.get("coordinates")
            if not coords:
                continue
            lon, lat = coords[0], coords[1]
            asset_id = f"bmc_{i}"
            if db.query(DrainageAsset).filter_by(id=asset_id).first():
                continue
            props = f.get("properties") or {}
            db.add(DrainageAsset(
                id=asset_id,
                asset_type="storm_water_drain",
                name=props.get("NAME") or props.get("name") or f"BMC Asset {i}",
                latitude=lat, longitude=lon,
                # BMC's GIS layer doesn't expose hydraulic capacity — estimate
                # a reasonable placeholder until real capacity data is sourced.
                capacity_lps=round(random.uniform(800, 2500), 1),
                current_flow_lps=0.0,
                source="BMC_GIS",
            ))
            created += 1
    except Exception as exc:
        print(f"[seed] BMC GIS unavailable ({exc}), using synthetic drainage assets instead.")
        for z in ZONES:
            for asset in _synthetic_assets_for_zone(z):
                if db.query(DrainageAsset).filter_by(id=asset.id).first():
                    continue
                db.add(asset)
                created += 1

    db.commit()
    return created


def seed_field_teams(db) -> int:
    demo_teams = [
        {"id": "team_alpha", "name": "Alpha Response Unit", "zone": "kurla"},
        {"id": "team_bravo", "name": "Bravo Response Unit", "zone": "sion"},
        {"id": "team_charlie", "name": "Charlie Response Unit", "zone": "andheri_east"},
        {"id": "team_delta", "name": "Delta Response Unit", "zone": "dadar"},
        {"id": "team_echo", "name": "Echo Response Unit", "zone": "bandra"},
    ]
    zones_by_id = {z["id"]: z for z in ZONES}
    created = 0
    for t in demo_teams:
        if db.query(FieldTeam).filter_by(id=t["id"]).first():
            continue
        z = zones_by_id[t["zone"]]
        db.add(FieldTeam(
            id=t["id"], name=t["name"], status="standby",
            latitude=z["lat"], longitude=z["lon"],
        ))
        created += 1
    db.commit()
    return created


async def main():
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    try:
        cells = seed_spatial_cells(db)
        assets = await seed_drainage_assets(db)
        teams = seed_field_teams(db)
        print(f"Seeded: {cells} spatial cells, {assets} drainage assets, {teams} field teams.")
    finally:
        db.close()


if __name__ == "__main__":
    asyncio.run(main())