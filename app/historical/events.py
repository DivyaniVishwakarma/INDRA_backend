"""
Verified historical Mumbai flood-event catalog.

This file stores event metadata only. Spatial flood extents must be supplied
as actual observation/reconstruction artifacts under data/historical/<id>/.
No synthetic flood polygons are generated here.
"""
from __future__ import annotations

EVENTS = [
    {
        "id": "mumbai_2005_07_26",
        "name": "26–27 July 2005 Mumbai Flood",
        "start": "2005-07-26T00:00:00+05:30",
        "end": "2005-07-27T23:59:59+05:30",
        "type": "historical_extreme_event",
        "verified_rainfall": [
            {"station": "Santacruz", "rainfall_24h_mm": 944.2},
            {"station": "Vihar Lake", "rainfall_24h_mm": 1049.0},
            {"station": "Bhandup", "rainfall_24h_mm": 815.0},
            {"station": "Dharavi", "rainfall_24h_mm": 493.0},
            {"station": "Colaba", "rainfall_24h_mm": 73.4},
        ],
        "artifacts": {
            "rainfall_csv": "rainfall.csv",
            "flood_extent_geojson": "flood_extent.geojson",
        },
        "source_note": "IMD historical rainfall records; spatial flood extent must be provided from a verified BMC/remote-sensing product.",
    },
    {
        "id": "mumbai_2017_08_29",
        "name": "29 August 2017 Mumbai Flood",
        "start": "2017-08-29T00:00:00+05:30",
        "end": "2017-08-30T23:59:59+05:30",
        "type": "historical_event",
        "verified_rainfall": [],
        "artifacts": {
            "rainfall_csv": "rainfall.csv",
            "flood_extent_geojson": "flood_extent.geojson",
        },
        "source_note": "Event metadata; attach verified spatial observations before enabling extent replay.",
    },
    {
        "id": "mumbai_2021_07_18",
        "name": "18 July 2021 Heavy Rain Event",
        "start": "2021-07-18T00:00:00+05:30",
        "end": "2021-07-19T23:59:59+05:30",
        "type": "historical_event",
        "verified_rainfall": [],
        "artifacts": {
            "rainfall_csv": "rainfall.csv",
            "flood_extent_geojson": "flood_extent.geojson",
        },
        "source_note": "NRSC/ISRO published heavy-rain affected-area product exists for this event; use the verified raster/vector product for replay.",
    },
]


def list_events() -> list[dict]:
    return EVENTS


def get_event(event_id: str) -> dict:
    for event in EVENTS:
        if event["id"] == event_id:
            return event
    raise KeyError(event_id)
