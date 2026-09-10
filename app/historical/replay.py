"""
Historical event replay service.

The replay API returns only artifacts that actually exist on disk.
"""
from __future__ import annotations

import csv
import json
from pathlib import Path

from .events import get_event

DATA_ROOT = Path(__file__).resolve().parents[3] / "data" / "historical"


def event_dir(event_id: str) -> Path:
    return DATA_ROOT / event_id


def load_replay(event_id: str) -> dict:
    event = get_event(event_id)
    folder = event_dir(event_id)

    rainfall = []
    rainfall_path = folder / event["artifacts"]["rainfall_csv"]
    if rainfall_path.exists():
        with rainfall_path.open("r", encoding="utf-8") as f:
            rainfall = list(csv.DictReader(f))

    flood_extent = None
    extent_path = folder / event["artifacts"]["flood_extent_geojson"]
    if extent_path.exists():
        flood_extent = json.loads(extent_path.read_text(encoding="utf-8"))

    return {
        "event": event,
        "available": {
            "rainfall": bool(rainfall),
            "flood_extent": flood_extent is not None,
        },
        "rainfall": rainfall,
        "flood_extent": flood_extent,
        "replay_status": (
            "complete"
            if rainfall and flood_extent is not None
            else "partial_artifacts_missing"
        ),
    }
