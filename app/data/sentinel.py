"""
Copernicus Sentinel-1 historical flood-observation adapter.

Sentinel-1 SAR is appropriate for reconstructing inundation because it works
through cloud cover. The API is deliberately credential/configuration based:
do not hard-code a third-party token or pretend an unverified polygon is
observed flooding.

For production, configure a Copernicus Data Space / Sentinel Hub compatible
catalog/search endpoint and credentials.
"""
from __future__ import annotations

import os
from typing import Any

import httpx

CATALOG_URL = os.getenv("SENTINEL_CATALOG_URL", "")
CLIENT_ID = os.getenv("SENTINEL_CLIENT_ID", "")
CLIENT_SECRET = os.getenv("SENTINEL_CLIENT_SECRET", "")


async def search(
    *,
    start: str,
    end: str,
    bbox: str = "72.75,18.85,73.05,19.35",
    collection: str = "sentinel-1",
) -> dict[str, Any]:
    if not CATALOG_URL:
        return {
            "available": False,
            "source": "Copernicus Sentinel-1",
            "reason": "SENTINEL_CATALOG_URL is not configured",
            "search": {"start": start, "end": end, "bbox": bbox, "collection": collection},
        }

    params = {
        "start": start,
        "end": end,
        "bbox": bbox,
        "collection": collection,
    }

    auth = None
    if CLIENT_ID and CLIENT_SECRET:
        auth = (CLIENT_ID, CLIENT_SECRET)

    async with httpx.AsyncClient(timeout=60.0) as client:
        response = await client.get(CATALOG_URL, params=params, auth=auth)
        response.raise_for_status()
        return response.json()


def source_metadata() -> dict[str, Any]:
    return {
        "source": "Copernicus Sentinel-1",
        "configured": bool(CATALOG_URL),
        "purpose": "historical observed/reconstructed inundation evidence",
    }
