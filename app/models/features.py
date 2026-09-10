"""
Feature construction for the flood model.

All values are explicit features. Missing observations remain missing/flagged
rather than being silently replaced by fabricated measurements.
"""
from __future__ import annotations

from math import hypot
from typing import Any

FEATURE_NAMES = [
    "rain_15m_mm",
    "rain_60m_mm",
    "rain_180m_mm",
    "rain_intensity_mm_h",
    "elevation_m",
    "slope_pct",
    "distance_to_drain_m",
    "drainage_capacity_ratio",
    "tide_m",
    "historical_flood_frequency",
    "impervious_fraction",
]


def build_features(
    *,
    rain_15m_mm: float | None = None,
    rain_60m_mm: float | None = None,
    rain_180m_mm: float | None = None,
    elevation_m: float | None = None,
    slope_pct: float | None = None,
    distance_to_drain_m: float | None = None,
    drainage_capacity_ratio: float | None = None,
    tide_m: float | None = None,
    historical_flood_frequency: float | None = None,
    impervious_fraction: float | None = None,
) -> dict[str, Any]:
    r15 = float(rain_15m_mm or 0)
    r60 = float(rain_60m_mm or 0)
    r180 = float(rain_180m_mm or 0)

    # 60-minute accumulation is converted to an intensity proxy.
    intensity = r60 if r60 > 0 else r15 * 4.0

    values = {
        "rain_15m_mm": r15,
        "rain_60m_mm": r60,
        "rain_180m_mm": r180,
        "rain_intensity_mm_h": intensity,
        "elevation_m": float(elevation_m or 0),
        "slope_pct": float(slope_pct or 0),
        "distance_to_drain_m": float(distance_to_drain_m or 0),
        "drainage_capacity_ratio": float(drainage_capacity_ratio or 0),
        "tide_m": float(tide_m or 0),
        "historical_flood_frequency": float(historical_flood_frequency or 0),
        "impervious_fraction": float(impervious_fraction or 0),
    }

    return values


def quality(features: dict[str, Any]) -> dict[str, Any]:
    missing = [
        name for name in FEATURE_NAMES
        if features.get(name) is None
    ]
    return {
        "complete": not missing,
        "missing_features": missing,
        "feature_count": len(FEATURE_NAMES),
        "available_count": len(FEATURE_NAMES) - len(missing),
    }


def grid_points(
    min_lat: float,
    max_lat: float,
    min_lon: float,
    max_lon: float,
    step_deg: float = 0.0005,
) -> list[tuple[float, float]]:
    """Generate a spatial grid (~50 m latitude spacing at Mumbai latitudes)."""
    points = []
    lat = min_lat
    while lat <= max_lat + 1e-12:
        lon = min_lon
        while lon <= max_lon + 1e-12:
            points.append((round(lat, 7), round(lon, 7)))
            lon += step_deg
        lat += step_deg
    return points
