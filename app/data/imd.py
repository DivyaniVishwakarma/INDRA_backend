"""
IMD Mumbai data adapter.

The official RMC Mumbai site exposes current Mumbai observations and rainfall
products. This adapter intentionally does not invent station-level values.

For production station APIs, set IMD_CURRENT_API_URL to the IMD endpoint
available to your deployment and IMD_STATION_IDS to a comma-separated list.
"""
from __future__ import annotations

import os
from datetime import datetime, timezone
from typing import Any
import httpx

IMD_HOME = "https://mausam.imd.gov.in/mumbai/"
IMD_RAINFALL = "https://mausam.imd.gov.in/mumbai/rainfall_info.php"
IMD_URBAN = "https://mausam.imd.gov.in/mumbaiums/"

STATIONS = {
    "mumbai_colaba": {"name": "Mumbai-Colaba", "lat": 18.9067, "lon": 72.8147},
    "mumbai_santacruz": {"name": "Mumbai-Santacruz", "lat": 19.0896, "lon": 72.8656},
    "worli": {"name": "Worli", "lat": 18.9986, "lon": 72.8183},
    "powai": {"name": "Powai", "lat": 19.1176, "lon": 72.9060},
    "kurla": {"name": "Kurla", "lat": 19.0726, "lon": 72.8793},
    "bandra_kurla": {"name": "Bandra Kurla", "lat": 19.0607, "lon": 72.8691},
    "borivali": {"name": "Borivali", "lat": 19.2307, "lon": 72.8567},
    "kandivali": {"name": "Kandivali", "lat": 19.2041, "lon": 72.8526},
    "malad": {"name": "Malad", "lat": 19.1864, "lon": 72.8481},
    "mulund": {"name": "Mulund", "lat": 19.1726, "lon": 72.9425},
}


async def fetch_urban_page() -> str:
    """Fetch the official Greater Mumbai urban weather page."""
    async with httpx.AsyncClient(timeout=30.0) as client:
        response = await client.get(IMD_URBAN)
        response.raise_for_status()
        return response.text


async def fetch_current_api() -> dict[str, Any] | None:
    """
    Optional IMD API adapter.

    Do not silently fall back to fake values. If the deployment has an
    authorized/public IMD API endpoint, configure it through the environment.
    """
    url = os.getenv("IMD_CURRENT_API_URL")
    if not url:
        return None

    station_ids = [
        x.strip() for x in os.getenv("IMD_STATION_IDS", "").split(",") if x.strip()
    ]
    params = {}
    if station_ids:
        params["ids"] = ",".join(station_ids)

    async with httpx.AsyncClient(timeout=30.0) as client:
        response = await client.get(url, params=params)
        response.raise_for_status()
        return response.json()


def source_record(source: str, observed_at: str | None = None) -> dict[str, Any]:
    return {
        "source": source,
        "observed_at": observed_at or datetime.now(timezone.utc).isoformat(),
        "is_observed": True,
    }


def source_metadata() -> dict[str, Any]:
    """
    Metadata about the IMD data source, used by /api/live/sources.
    Mirrors the shape returned by bmc_gis.source_metadata() and
    gpm.source_metadata() so /api/live/sources stays consistent.
    """
    return {
        "source": "IMD (India Meteorological Department) - Mumbai",
        "urban_page": IMD_URBAN,
        "rainfall_page": IMD_RAINFALL,
        "home_page": IMD_HOME,
        "stations": list(STATIONS.keys()),
        # True only if a real production station API has been configured
        # via env vars — no fake/mock fallback, consistent with the rest
        # of this file's intent.
        "configured": bool(os.getenv("IMD_CURRENT_API_URL")),
    }