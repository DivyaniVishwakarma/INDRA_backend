"""
NASA GPM IMERG adapter.

IMERG is useful for historical/near-real-time precipitation, but its native
grid is much coarser than a street. This connector therefore returns the
source product and lets the feature-fusion layer combine it with gauges.

NASA Earthdata credentials/endpoints should be configured explicitly. No fake
rainfall endpoint is used.
"""
from __future__ import annotations

import os
from typing import Any

import httpx

GPM_URL = os.getenv("GPM_API_URL", "")
GPM_TOKEN = os.getenv("GPM_API_TOKEN", "")


async def fetch(url: str | None = None, params: dict[str, Any] | None = None) -> Any:
    target = url or GPM_URL
    if not target:
        return {
            "available": False,
            "source": "NASA GPM IMERG",
            "reason": "GPM_API_URL is not configured",
        }

    headers = {}
    if GPM_TOKEN:
        headers["Authorization"] = f"Bearer {GPM_TOKEN}"

    async with httpx.AsyncClient(timeout=60.0) as client:
        response = await client.get(target, params=params or {}, headers=headers)
        response.raise_for_status()
        content_type = response.headers.get("content-type", "")
        return response.json() if "json" in content_type else response.text


def source_metadata() -> dict[str, Any]:
    return {
        "source": "NASA GPM IMERG",
        "configured": bool(GPM_URL),
        "native_resolution_note": "IMERG is not street-level; fuse with ground observations before hyperlocal mapping.",
    }
